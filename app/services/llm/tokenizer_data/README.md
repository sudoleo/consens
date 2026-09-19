# Offline vocabulary

`cl100k_base.tiktoken.gz` contains the unchanged public tiktoken vocabulary,
compressed with gzip (mtime 0). Source:
https://openaipublic.blob.core.windows.net/encodings/cl100k_base.tiktoken

Uncompressed SHA-256:
`223921b76ee99bde995b7ff738513eef100fb51d18c93597a113bcffe865b2a7`

Pattern and encoding format: https://github.com/openai/tiktoken/tree/0.12.0
The upstream MIT license is included in `LICENSE`.

`agent_tokens.py` verifies and loads this file locally. Do not replace it with
`get_encoding()`, which can download data on the first request. This common
tokenizer plus a margin is an admission estimate across providers, never billing.
