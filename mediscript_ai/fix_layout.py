import re

with open('C:\\Users\\HP\\Downloads\\Sanjeevani\\mediscript_ai\\app\\templates\\doctor_xray.html', 'r', encoding='utf-8') as f:
    text = f.read()

# The layout starts at <div class="result-grid"> and ends before <!-- ═══════════════════════════════════════════════════════════
#      PAGE: HISTORY

start_marker = '<div class="result-grid">'
end_marker = '<!-- ═══════════════════════════════════════════════════════════\n     PAGE: HISTORY'

start_idx = text.find(start_marker)
end_idx = text.find(end_marker)

if start_idx == -1 or end_idx == -1:
    print("Could not find markers")
    exit(1)

content = text[start_idx:end_idx]

# Extract Images Block
img_start = content.find('  <!-- Left: Images -->')
img_end = content.find('  <!-- Right: Findings -->')
img_block = content[img_start:img_end].strip()

# Extract Findings Block
find_start = img_end
find_end = content.find('<!-- AI Explanation -->')
# wait, result-grid is closed before AI explanation. So the closing </div> is right before find_end!
# Let's find the closing </div> of result-grid.
# It should be around `</div>\n\n<!-- AI Explanation -->`
closing_grid_idx = content.rfind('</div>', find_start, find_end)
find_block = content[find_start:closing_grid_idx].strip()

# Extract AI Explanation Block
ai_start = content.find('<!-- AI Explanation -->')
ai_end = content.find('<!-- AI Chat -->')
ai_block = content[ai_start:ai_end].strip()

# Extract AI Chat Block
chat_start = content.find('<!-- AI Chat -->')
chat_end = content.find('<!-- Doctor Verification -->')
chat_block = content[chat_start:chat_end].strip()

# Extract Verification Block
veri_start = content.find('<!-- Doctor Verification -->')
veri_end = len(content)
veri_block = content[veri_start:veri_end].strip()

# Remove mb-4/margin-top from moving blocks to ensure gap doesn't double up
ai_block = ai_block.replace('class="ai-report-box mb-4"', 'class="ai-report-box"')
chat_block = chat_block.replace('class="doc-card mb-4"', 'class="doc-card"')

new_layout = f"""<div class="xray-hero" style="align-items: start;">
  <!-- Left Column -->
  <div style="display: flex; flex-direction: column; gap: 24px;">
    {img_block}
    
    {ai_block}
  </div>

  <!-- Right Column -->
  <div style="display: flex; flex-direction: column; gap: 24px;">
    {find_block}
    
    {chat_block}
    
    {veri_block}
  </div>
</div>

"""

new_text = text[:start_idx] + new_layout + text[end_idx:]

with open('C:\\Users\\HP\\Downloads\\Sanjeevani\\mediscript_ai\\app\\templates\\doctor_xray.html', 'w', encoding='utf-8') as f:
    f.write(new_text)

print("Layout updated.")
