"""Regression test for the supplied two-column graphic design resume."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from resume_parser import parse_resume

def test_graphic_design_resume():
    import fitz
    pdf=Path(__file__).resolve().parents[1] / 'fixtures' / 'graphic_design_resume.pdf'
    with fitz.open(pdf) as doc:
        blocks=[]
        for page_no,page in enumerate(doc,1):
            for block in page.get_text('dict')['blocks']:
                for line in block.get('lines',[]):
                    txt=''.join(span['text'] for span in line['spans']).strip()
                    if txt:
                        blocks.append({'BlockType':'LINE','Page':page_no,'Text':txt,
                            'Geometry':{'BoundingBox':{'Top':line['bbox'][1]/page.rect.height,'Left':line['bbox'][0]/page.rect.width}}})
        result=parse_resume('\n'.join(page.get_text() for page in doc),blocks)
    assert {'Adobe Creative Suite','Figma','Procreate','Google Fonts','Coolors','Canva'} <= set(result['skills'])
    assert 'PixelPulse Exhibit' in result['projects']
    assert 'DesignCon Case Study' in result['projects']
    assert 'Bachelor of Fine Arts' in result['education']
    assert 'PixelPulse Exhibit' not in result['education']
    assert 'PixelPulse Exhibit' not in result['skills']
    assert 'Figma' not in result['education']
    assert 'ASHLEY CLARK' == result['detected_name']
