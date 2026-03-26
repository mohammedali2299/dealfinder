from PIL import Image
import httpx
import redis
import json
import os
from io import BytesIO
from transformers import CLIPProcessor, CLIPModel
import torch

model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32")
processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")

redis_client = redis.Redis(host="localhost", port=6379, decode_responses=True)

def get_image_embedding(img):
    inputs = processor(images=img, return_tensors="pt")
    with torch.no_grad():
        embedding = model.get_image_features(**inputs)
    return embedding / embedding.norm(dim=-1, keepdim=True)  # normalize

VALID_EXTENSIONS = {".jpg"}
                    
def load_reference_hashes(folder="reference_chairs", negative_folder="reference_chairs_negative"):
    references = {}
    for filename in os.listdir(folder):
        ext = os.path.splitext(filename)[1].lower()
        if ext not in VALID_EXTENSIONS:
            continue
        chair_name = "_".join(filename.split("_")[:-1])
        filepath = os.path.join(folder, filename)
        img = Image.open(filepath).convert("RGB")
        embedding = get_image_embedding(img)
        if chair_name not in references:
            references[chair_name] = []
        references[chair_name].append(embedding)

    negatives = []
    if os.path.exists(negative_folder):
        for filename in os.listdir(negative_folder):
            ext = os.path.splitext(filename)[1].lower()
            if ext not in VALID_EXTENSIONS:
                continue
            filepath = os.path.join(negative_folder, filename)
            img = Image.open(filepath).convert("RGB")
            negatives.append(imagehash.phash(img) if False else get_image_embedding(img))

    print(f"Loaded {len(references)} target chairs, {len(negatives)} negative examples")
    return references, negatives


def is_matching_chair(image_url, references, negatives, threshold=0.92, negative_threshold=0.90):
    try:
        response = httpx.get(image_url, timeout=10)
        img = Image.open(BytesIO(response.content)).convert("RGB")
        tiles = get_image_tiles(img)

        for chair_name, embeddings in references.items():
            best_score = 0
            for tile in tiles:
                tile_embedding = get_image_embedding(tile)

                # check against negatives first — reject early if too similar
                if negatives:
                    negative_score = max(
                        torch.nn.functional.cosine_similarity(tile_embedding, neg).item()
                        for neg in negatives
                    )
                    if negative_score >= negative_threshold:
                        print(f"    Rejected by negative example — score: {negative_score:.3f}")
                        continue

                score = max(
                    torch.nn.functional.cosine_similarity(tile_embedding, ref).item()
                    for ref in embeddings
                )
                best_score = max(best_score, score)

            print(f"    {chair_name} — best similarity: {best_score:.3f}")
            if best_score >= threshold:
                return True, chair_name, best_score

        return False, None, None
    except Exception as e:
        print(f"    Error: {e}")
        return False, None, None

def get_image_tiles(img, tile_size=224, overlap=0.5):
    tiles = [img]  # always include the full image
    width, height = img.size
    step = int(tile_size * (1 - overlap))

    for y in range(0, height - tile_size + 1, step):
        for x in range(0, width - tile_size + 1, step):
            tile = img.crop((x, y, x + tile_size, y + tile_size))
            tiles.append(tile)
    return tiles

reference_hashes, negatives = load_reference_hashes()

print("Waiting for listings...")
while True:
    job = redis_client.brpop("listings:queue", timeout=30)
    if job is None:
        print("Queue empty — waiting...")
        continue

    listing = json.loads(job[1])
    print(f"\nProcessing: {listing['title']} — {listing['price']}")

    matched = False
    for image_url in listing["image_urls"]:
        match, chair_name, score = is_matching_chair(image_url, reference_hashes, negatives)
        if match:
            print(f"  ✅ MATCH — {chair_name} — similarity: {score:.3f}")
            print(f"  {listing['url']}")
            matched = True
            break

    if not matched:
        print(f"  No match")