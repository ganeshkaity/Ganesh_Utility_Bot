import requests

def clean_url(url):
    return url.split("?")[0]

def get_reel_data(url):
    apis = [
        f"https://api.cobalt.tools/api/json",
    ]

    for api in apis:
        try:
            print(f"\n🔄 Trying API:\n{api}")

            payload = {
                "url": url
            }

            headers = {
                "Content-Type": "application/json"
            }

            res = requests.post(api, json=payload, headers=headers, timeout=15)

            print("📡 Status:", res.status_code)

            data = res.json()

            if data:
                return data

        except Exception as e:
            print("❌ API failed:", e)

    return {"error": "All APIs failed"}

def extract_video(data):
    try:
        return data["url"]
    except:
        return None

def main():
    print("=== Instagram Reel Downloader ===")

    url = input("Enter Instagram Reel URL: ").strip()

    if not url:
        print("❌ No URL entered")
        return

    url = clean_url(url)

    print("\n🔗 Clean URL:", url)

    data = get_reel_data(url)

    print("\n=== JSON Response ===")
    print(data)

    video_url = extract_video(data)

    if video_url:
        print("\n🎬 Video URL:")
        print(video_url)
    else:
        print("\n⚠️ Could not extract video URL")

if __name__ == "__main__":
    main()