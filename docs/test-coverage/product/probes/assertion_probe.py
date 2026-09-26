"""Opt-in, process-local audit mutations. Never edits production source files."""
import ast
import io
import os
import textwrap


def pytest_configure(config):
    probe = os.environ.get('AUDIT_PROBE')
    if probe and os.environ.get('UNIT_TEST_MODE') != '1':
        raise RuntimeError('Audit probes require UNIT_TEST_MODE=1')
    if probe == 'memory_undo_revision':
        import inspect
        from app.services import memory_edit
        tree = ast.parse(textwrap.dedent(inspect.getsource(memory_edit.FirestoreMemoryEditRepository.undo)))
        changed = 0
        for node in ast.walk(tree):
            if isinstance(node, ast.If) and 'current_revision !=' in ast.unparse(node.test):
                node.test = ast.Constant(False)
                changed += 1
        if changed != 1:
            raise RuntimeError(f'Expected one audited revision guard, found {changed}; re-review source')
        namespace = dict(memory_edit.__dict__)
        exec(compile(ast.fix_missing_locations(tree), '<audit-undo-mutation>', 'exec'), namespace)
        memory_edit.FirestoreMemoryEditRepository.undo = namespace['undo']
    elif probe == 'og_blank':
        from app.services import og_image
        from PIL import Image

        def blank(**kwargs):
            buffer = io.BytesIO()
            Image.new('RGB', (1200, 630), 'white').save(buffer, format='PNG')
            return buffer.getvalue()

        og_image._cache.clear()
        og_image.render_share_card = blank
    elif probe:
        raise RuntimeError('Unknown audit probe')
