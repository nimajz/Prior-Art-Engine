import os
from sentence_transformers import SentenceTransformer

# معرفی شناسه دقیق مدل
BI_ENCODER_ID = "BAAI/bge-small-en-v1.5"

def load_bi_encoder():
    print(f"🔄 Loading Bi-Encoder model: {BI_ENCODER_ID}...")
    try:
        # لود کردن مدل (در اولین اجرا دانلود می‌شود و دفعات بعدی از کش خوانده می‌شود)
        model = SentenceTransformer(BI_ENCODER_ID)
        print("✅ Bi-Encoder model loaded successfully!")
        return model
    except Exception as e:
        print(f"❌ Failed to load model: {e}")
        return None

# تست محلی تبدیل متن به بردار
if __name__ == "__main__":
    encoder = load_bi_encoder()
    if encoder:
        sample_text = "autonomous drone-based crop monitoring system"
        # تولید بردار (Vector Embedding)
        embedding = encoder.encode(sample_text)
        print(f"Vector Dimensions: {len(embedding)}") # برای این مدل باید 384 باشد