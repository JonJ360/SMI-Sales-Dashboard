from pathlib import Path
import re

def test_pixel_fill_has_no_continuous_highlight_over_the_segment_gaps():
    css=(Path(__file__).resolve().parents[1]/'report-toolbar.css').read_text()
    fill=re.search(r'\.refresh-progress-line\{([^}]+)\}',css).group(1)
    assert 'repeating-linear-gradient' in fill
    assert 'box-shadow' not in fill
