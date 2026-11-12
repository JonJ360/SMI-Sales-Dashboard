from pathlib import Path


def test_management_misc_disclosure_includes_verified_codes_and_josh_exemption():
    html = (Path(__file__).resolve().parents[1] / 'index.html').read_text(encoding='utf-8')
    note = html.split('Miscellaneous merchandise · Management estimate, not supplier actual', 1)[1].split('</details>', 1)[0]
    for code in ('204100', '46300', 'RV41390'):
        assert code in note
    assert 'Josh' in note and 'Above All For' in note
    assert '50% of source extended line sales' in note
    assert '41393 (DO NOT USE) remains held' in note
    assert 'GP and source lines are unchanged' in note
