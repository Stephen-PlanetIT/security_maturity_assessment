from consultation_helpers import sanitise_nested

def test_sanitise_nested_handles_nested_structures():
    obj = {'a': 'foo\u200B', 'b': ['x\u2060', {'c': 'y\n\n\n'}]}
    out = sanitise_nested(obj)
    assert out['a'] == 'foo'
    assert out['b'][0] == 'x'
    assert out['b'][1]['c'] == 'y\n\n'
