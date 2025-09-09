from services.video_service import VideoService


def main():
    # Hard coded test files
    video_file = "downloads/y3yAVZk3tyA.mp4"
    thumbnail_file = "downloads/y3yAVZk3tyA.webp"

    # Initialize video service and test
    video_service = VideoService()
    result = video_service.prepare_video(video_file, thumbnail_file)

    if result:
        print(f"Success: {result}")
    else:
        print("Failed")


if __name__ == "__main__":
    main()
