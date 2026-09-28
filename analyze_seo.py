import re

with open('frontend/index.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Find body tag and surrounding context
body_match = re.search(r'<body[^>]*>', content)
if body_match:
    start = max(0, body_match.start() - 100)
    end = min(len(content), body_match.end() + 3000)
    print('=== BODY TAG AREA ===')
    print(content[start:end])
    print()

# Find all h1, h2, h3 tags
print('=== HEADINGS ===')
for m in re.finditer(r'<h[1-3][^>]*>.*?</h[1-3]>', content, re.DOTALL):
    line_num = content[:m.start()].count('\n') + 1
    print(f'Line {line_num}: {m.group()[:200]}')

# Find all img tags
print()
print('=== IMAGES ===')
for m in re.finditer(r'<img[^>]*>', content):
    line_num = content[:m.start()].count('\n') + 1
    print(f'Line {line_num}: {m.group()[:200]}')

# Find semantic elements
print()
print('=== SEMANTIC ELEMENTS ===')
for tag in ['<main', '<nav', '<article', '<section', '<header', '<footer', '<aside']:
    matches = list(re.finditer(re.escape(tag), content))
    if matches:
        for m in matches[:5]:
            line_num = content[:m.start()].count('\n') + 1
            snippet = content[m.start():m.start()+150]
            print(f'{tag} Line {line_num}: {snippet[:150]}')
    else:
        print(f'{tag}: NOT FOUND')

# Find closing tags
print()
print('=== CLOSING TAGS ===')
for tag in ['</main>', '</nav>', '</article>', '</section>', '</header>', '</footer>', '</aside>', '</body>', '</html>']:
    matches = list(re.finditer(re.escape(tag), content))
    if matches:
        for m in matches[:3]:
            line_num = content[:m.start()].count('\n') + 1
            print(f'{tag} Line {line_num}')
    else:
        print(f'{tag}: NOT FOUND')

# Check for aria attributes
print()
print('=== ARIA ATTRIBUTES ===')
aria_matches = list(re.finditer(r'aria-[a-z]+="[^"]*"', content))
if aria_matches:
    for m in aria_matches[:10]:
        line_num = content[:m.start()].count('\n') + 1
        print(f'Line {line_num}: {m.group()}')
else:
    print('No aria attributes found')

# Check for role attributes
print()
print('=== ROLE ATTRIBUTES ===')
role_matches = list(re.finditer(r'role="[^"]*"', content))
if role_matches:
    for m in role_matches[:10]:
        line_num = content[:m.start()].count('\n') + 1
        print(f'Line {line_num}: {m.group()}')
else:
    print('No role attributes found')

# Check for tabindex
print()
print('=== TABINDEX ===')
tabindex_matches = list(re.finditer(r'tabindex="[^"]*"', content))
if tabindex_matches:
    for m in tabindex_matches[:10]:
        line_num = content[:m.start()].count('\n') + 1
        print(f'Line {line_num}: {m.group()}')
else:
    print('No tabindex attributes found')

# Check for button elements
print()
print('=== BUTTONS ===')
button_matches = list(re.finditer(r'<button[^>]*>', content))
print(f'Total buttons: {len(button_matches)}')
for m in button_matches[:5]:
    line_num = content[:m.start()].count('\n') + 1
    print(f'Line {line_num}: {m.group()[:200]}')

# Check for links
print()
print('=== LINKS ===')
link_matches = list(re.finditer(r'<a[^>]*>', content))
print(f'Total links: {len(link_matches)}')
for m in link_matches[:5]:
    line_num = content[:m.start()].count('\n') + 1
    print(f'Line {line_num}: {m.group()[:200]}')

# Check for divs with onclick (potential accessibility issues)
print()
print('=== DIVS WITH ONCLICK ===')
onclick_divs = list(re.finditer(r'<div[^>]*onclick[^>]*>', content))
print(f'Total divs with onclick: {len(onclick_divs)}')
for m in onclick_divs[:5]:
    line_num = content[:m.start()].count('\n') + 1
    print(f'Line {line_num}: {m.group()[:200]}')