import re

with open('C:\\Users\\HP\\Downloads\\Sanjeevani\\mediscript_ai\\app\\templates\\doctor_xray.html', 'r', encoding='utf-8') as f:
    text = f.read()

# We need to find the specific blocks in page == 'upload'
# The block starts with <div class="xray-hero">
# Ends just before <!-- ═══════════════════════════════════════════════════════════
#      PAGE: RESULT

start_marker = '<div class="xray-hero">'
end_marker = '<!-- ═══════════════════════════════════════════════════════════\n     PAGE: RESULT'

start_idx = text.find(start_marker)
end_idx = text.find(end_marker)

if start_idx == -1 or end_idx == -1:
    print("Could not find markers")
    exit(1)

content = text[start_idx:end_idx]

# Extract Upload Zone
upload_start = content.find('  <!-- Upload zone -->')
preview_start = content.find('  <!-- Preview + controls -->')
upload_block = content[upload_start:preview_start].strip()

# Extract Preview block.
recent_start = content.find('<!-- Recent scans -->')
preview_block = content[preview_start:recent_start].strip()
# `preview_block` ends with `</div>\n</div>`. We need to strip the outer </div> which closes xray-hero.
if preview_block.endswith('</div>\n</div>'):
    preview_block = preview_block[:-6].strip()

# Extract Recent Scans
recent_block = content[recent_start:].strip()

new_layout = f"""<div class="xray-hero" style="align-items: start;">
  <!-- Left Column -->
  <div style="display: flex; flex-direction: column; gap: 24px;">
    {upload_block}

    {recent_block}
  </div>

  <!-- Right Column -->
  <div style="display: flex; flex-direction: column; gap: 24px;">
    {preview_block}
  </div>
</div>

"""

new_text = text[:start_idx] + new_layout + text[end_idx:]

with open('C:\\Users\\HP\\Downloads\\Sanjeevani\\mediscript_ai\\app\\templates\\doctor_xray.html', 'w', encoding='utf-8') as f:
    f.write(new_text)

print("Upload Layout updated.")
