import sys, cv2
for p in sys.argv[1:]:
    c = cv2.VideoCapture(p); n = int(c.get(7)); f = c.get(5)
    print(p.split("\\")[-3] if "\\" in p else p, f"{int(c.get(3))}x{int(c.get(4))}", f"{f:.1f}fps", f"{n} frames", f"{n/f/60:.1f} min")
