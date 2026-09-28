import zipfile, io, csv

z = zipfile.ZipFile(r'c:\Users\matth\OneDrive\Documents\OpenSourceMed\Physiological Fitness Landscape\backend\Loinc_2.83.zip')
data = z.read('LoincTable/Loinc.csv').decode('utf-8')
reader = csv.reader(io.StringIO(data))
rows = list(reader)

out = []
out.append('TOTAL ROWS: %d' % len(rows))
out.append('HEADER:')
for i, h in enumerate(rows[0]):
    out.append('  [%d] %s' % (i, h))
out.append('')
out.append('SAMPLE ROW 1:')
for i, v in enumerate(rows[1]):
    out.append('  [%d] %s = %s' % (i, rows[0][i], v))

with open(r'c:\Users\matth\OneDrive\Documents\OpenSourceMed\Physiological Fitness Landscape\backend\_loinc_inspect.txt', 'w') as f:
    f.write('\n'.join(out))
print('done')