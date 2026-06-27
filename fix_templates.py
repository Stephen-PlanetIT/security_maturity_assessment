"""Repair split Jinja2 tags in maturity assessment DOCX templates."""
import zipfile, re, io, shutil, os

def fix_template(path_in, path_out=None):
    """Fix all instances of {% if not loop.last %}...{% endif %} split across XML runs."""
    if path_out is None:
        path_out = path_in
    
    with zipfile.ZipFile(path_in, 'r') as zin:
        doc_xml = zin.read('word/document.xml')
        all_files = {name: zin.read(name) for name in zin.namelist()}
    
    text = doc_xml.decode('utf-8', errors='replace')
    
    # Pattern: find the broken pattern where </w:t></w:r><w:r><w:br/><w:t> sits between if/endif
    broken_pattern = re.compile(
        r'(\{%\s*if not loop\.last\s*%\})</w:t></w:r><w:r><w:br/><w:t>(\{%\s*endif\s*%\})',
        re.DOTALL
    )
    
    count = 0
    def replace_broken(m):
        nonlocal count
        count += 1
        return m.group(1) + '<w:br/>' + m.group(2)
    
    new_text = broken_pattern.sub(replace_broken, text)
    
    if count > 0:
        print(f"  Fixed {count} split Jinja2 tag(s) in {path_in}")
        new_xml = new_text.encode('utf-8')
        all_files['word/document.xml'] = new_xml
        
        # Write back
        with zipfile.ZipFile(path_out, 'w', zipfile.ZIP_DEFLATED) as zout:
            for name, data in all_files.items():
                zout.writestr(name, data)
        return True
    else:
        print(f"  No split tags found in {path_in} (already fixed or different issue)")
        return False

print("=== Fixing Maturity Assessment Templates ===")
fixed_any = False
for template in ['planet_it_maturity_assessment_template.docx', 'planet_it_maturity_assessment_template_v2.docx']:
    if fix_template(template):
        fixed_any = True

if fixed_any:
    print("\nTemplates fixed successfully.")
else:
    print("\nWARNING: No split tags found in either template.")