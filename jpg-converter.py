from PIL import Image
import os

folder = "reference_chairs"

for filename in os.listdir(folder):
    filepath = os.path.join(folder, filename)
    img = Image.open(filepath).convert("RGB")
    new_path = os.path.splitext(filepath)[0] + ".jpg"
    img.save(new_path, "JPEG")
    if not filename.endswith(".jpg"):
        os.remove(filepath)  # remove the original non-jpg
    print(f"Converted: {filename} → {os.path.basename(new_path)}")