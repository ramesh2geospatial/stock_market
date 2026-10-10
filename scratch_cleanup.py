"""Remove the duplicate old Vahan tab10 code from app.py."""
with open(r"d:\GeoNagrik\Dev\git\stock_market\app.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

print(f"Total lines before: {len(lines)}")

# Find the boundaries:
# The NEW code ends around line 1621 (the last line before the old duplicate)
# The old duplicate starts around line 1622 with `    st.markdown("""`
# The old duplicate ends just before "# TAB 11: AI PREDICTOR"

# Find where the old duplicate starts (the st.markdown with spider-header after our new code)
old_start = None
tab11_start = None

for i, line in enumerate(lines):
    # Find the old duplicate block: it's the second spider-header in tab10
    # Our new code already has a proper structure; the old one starts with st.markdown
    if i > 1620 and '🛵 Vahan EV Sales Report' in line and old_start is None:
        # Go back to find the st.markdown that starts this block
        j = i
        while j > 0 and 'st.markdown("""' not in lines[j]:
            j -= 1
        old_start = j
        print(f"Found old duplicate starting at line {old_start + 1}")
    
    if 'TAB 11: AI PREDICTOR' in line:
        # The "# ===" line is 2 lines before this
        tab11_start = i - 1  # The blank line before the === separator
        print(f"Found TAB 11 marker at line {i + 1}, will delete up to line {tab11_start + 1}")
        break

if old_start is not None and tab11_start is not None:
    # Remove lines from old_start to tab11_start (exclusive of tab11)
    new_lines = lines[:old_start] + lines[tab11_start:]
    
    with open(r"d:\GeoNagrik\Dev\git\stock_market\app.py", "w", encoding="utf-8") as f:
        f.writelines(new_lines)
    
    print(f"Removed {tab11_start - old_start} lines ({old_start+1} to {tab11_start+1})")
    print(f"Total lines after: {len(new_lines)}")
else:
    print("Could not find boundaries! No changes made.")
    print(f"old_start: {old_start}, tab11_start: {tab11_start}")
