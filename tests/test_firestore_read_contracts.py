"""Exercise the installed SDK's query/transaction/wire decoding, fully offline.

Only the RPC boundary is replaced. Real Client, Query, AggregationQuery,
Transaction and protobuf response decoding run exactly as in production.
"""

import json
from pathlib import Path
from unittest.mock import Mock

import pytest
from google.auth.credentials import AnonymousCredentials
from google.cloud.firestore_v1 import Client, _helpers
from google.cloud.firestore_v1.types import (
    BeginTransactionResponse,
    CommitResponse,
    Document,
    RunAggregationQueryResponse,
    RunQueryResponse,
    StructuredQuery,
)

from app.api.routers import pages


def offline_client():
    client = Client(project="demo-read-contract-test", credentials=AnonymousCredentials())
    rpc = Mock(spec=["begin_transaction", "run_query", "run_aggregation_query", "commit", "rollback"])
    rpc.begin_transaction.return_value = BeginTransactionResponse(transaction=b"read-snapshot")
    rpc.commit.return_value = CommitResponse()
    # Install before the SDK can initialize a transport/channel. No credentials
    # are loaded, and no real Firestore RPC is possible from this client.
    client._firestore_api_internal = rpc
    return client, rpc


def query_response(client, path, fields):
    return RunQueryResponse(document=Document(
        name=f"{client._database_string}/documents/{path}",
        fields=_helpers.encode_dict(fields),
    ))


def assert_read_only_snapshot(rpc):
    begin = rpc.begin_transaction.call_args.kwargs["request"]
    assert begin["options"]._pb.HasField("read_only")
    assert rpc.begin_transaction.call_count == 1
    for method in (rpc.run_query, rpc.run_aggregation_query):
        for call in method.call_args_list:
            assert call.kwargs["request"]["transaction"] == b"read-snapshot"
    assert rpc.commit.call_count == 1
    commit = rpc.commit.call_args.kwargs["request"]
    assert commit["transaction"] == b"read-snapshot"
    assert commit["writes"] == []
    rpc.rollback.assert_not_called()


@pytest.mark.parametrize("selections", [0, 4])
def test_leaderboard_sdk_uses_indexed_counts_and_one_read_only_snapshot(selections):
    db, rpc = offline_client()
    rpc.run_query.return_value = iter([
        query_response(db, "leaderboard/Grok-vintage", {"BestModel": 4}),
    ])

    def count_response(*, request, **kwargs):
        aggregation = request["structured_aggregation_query"]
        assert aggregation.aggregations[0].alias == "selections"
        assert aggregation.aggregations[0]._pb.HasField("count")
        filters = {
            item.field_filter.field.field_path: item.field_filter
            for item in aggregation.structured_query.where.composite_filter.filters
        }
        aliases = [value.string_value for value in filters["model"].value.array_value.values]
        count = selections if "Grok-vintage" in aliases else 0
        # integer_value=0 is decoded by the installed SDK as 0.0. This tests
        # the real decoding path, not a fake AggregationResult object.
        return iter([RunAggregationQueryResponse(
            result={"aggregate_fields": {"selections": {"integer_value": count}}},
        )])

    rpc.run_aggregation_query.side_effect = count_response

    assert pages._count_period_leaderboard(db) == ({"xAI / Grok": selections} if selections else {})

    assert_read_only_snapshot(rpc)
    assert rpc.run_query.call_count == 1
    catalog = rpc.run_query.call_args.kwargs["request"]["structured_query"]
    assert catalog.from_[0].collection_id == "leaderboard"
    assert not catalog._pb.HasField("where")
    assert rpc.run_aggregation_query.call_count == 9
    for call in rpc.run_aggregation_query.call_args_list:
        assert call.kwargs["retry"] is None
        assert call.kwargs["timeout"] == 10
        query = call.kwargs["request"]["structured_aggregation_query"].structured_query
        assert query.from_[0].collection_id == "model_votes"
        assert not query._pb.HasField("limit")
        assert query.where.composite_filter.op == StructuredQuery.CompositeFilter.Operator.AND
        filters = {
            item.field_filter.field.field_path: item.field_filter
            for item in query.where.composite_filter.filters
        }
        assert set(filters) == {"model", "vote_type", "created_at"}
        assert filters["vote_type"].op == StructuredQuery.FieldFilter.Operator.EQUAL
        assert filters["vote_type"].value.string_value == "BestModel"
        assert filters["model"].op == StructuredQuery.FieldFilter.Operator.IN
        assert 1 <= len(filters["model"].value.array_value.values) <= 30
        assert filters["created_at"].op == StructuredQuery.FieldFilter.Operator.GREATER_THAN_OR_EQUAL
        assert filters["created_at"].value.timestamp_value == pages._MODEL_PULSE_COMPARABLE_SINCE

    indexes = json.loads((Path(__file__).resolve().parents[1] / "firestore.indexes.json").read_text())
    assert any(
        index["collectionGroup"] == "model_votes"
        and index["queryScope"] == "COLLECTION"
        and index["fields"] == [
            {"fieldPath": "vote_type", "order": "ASCENDING"},
            {"fieldPath": "model", "order": "ASCENDING"},
            {"fieldPath": "created_at", "order": "ASCENDING"},
        ]
        for index in indexes["indexes"]
    )
