import unittest
from clipjet import InvalidLink, MediaUnavailable
from youtube_video import canonical_youtube_video, pick_youtube_video, verified_youtube_media_url


class YoutubeTests(unittest.TestCase):
    def test_url_forms(self):
        expected = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        for url in (
            "https://youtu.be/dQw4w9WgXcQ?t=4",
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=ignored",
            "https://m.youtube.com/shorts/dQw4w9WgXcQ?feature=share",
            "https://youtube.com/live/dQw4w9WgXcQ",
        ):
            with self.subTest(url=url):
                self.assertEqual(canonical_youtube_video(url), expected)

    def test_rejects_invalid_and_ambiguous(self):
        for url in (
            "http://youtube.com/watch?v=dQw4w9WgXcQ", "https://youtube.com.evil.com/watch?v=dQw4w9WgXcQ",
            "https://youtube.com@evil.com/watch?v=dQw4w9WgXcQ", "https://youtube.com:444/watch?v=dQw4w9WgXcQ",
            "https://youtu.be/abc", "https://youtube.com/watch?v=dQw4w9WgXcQ&v=abcdefghijk",
            "https://youtube.com/playlist?list=PLabc", "https://youtube.com/watch?v=dQw4w9WgXcQ#fragment",
            "https://youtube.com/watch?v=dQw4w9WgXcQ https://evil.com",
            "https://youtube.com/shorts/dQw4w9WgXcQ/extra",
        ):
            with self.subTest(url=url), self.assertRaises(InvalidLink):
                canonical_youtube_video(url)

    def test_googlevideo_host_check(self):
        self.assertTrue(verified_youtube_media_url("https://rr1---sn-ab.googlevideo.com/videoplayback?expire=123&sig=abc"))
        for url in ("https://googlevideo.com/videoplayback?x=1", "https://googlevideo.com.evil.org/videoplayback?x=1",
                    "http://rr.googlevideo.com/videoplayback?x=1", "https://user@rr.googlevideo.com/videoplayback?x=1",
                    "https://rr.googlevideo.com:8080/videoplayback?x=1", "https://rr.googlevideo.com/redirect?x=1"):
            with self.subTest(url=url):
                self.assertFalse(verified_youtube_media_url(url))

    def test_selects_progressive_and_small(self):
        base = "https://rr.googlevideo.com/videoplayback?itag="
        formats = [
            {"url":base + "18", "ext":"mp4", "vcodec":"avc1", "acodec":"mp4a", "height":360, "filesize":9_000_000},
            {"url":base + "22", "ext":"mp4", "vcodec":"avc1", "acodec":"mp4a", "height":720, "filesize":17_000_000},
            {"url":base + "37", "ext":"mp4", "vcodec":"avc1", "acodec":"mp4a", "height":1080, "filesize":10_000_000},
            {"url":base + "137", "ext":"mp4", "vcodec":"avc1", "acodec":"none", "height":720, "filesize":2_000_000},
            {"url":base + "999", "ext":"mp4", "vcodec":"avc1", "acodec":"mp4a", "height":720, "filesize":21_000_000},
        ]
        video=pick_youtube_video({"formats": formats, "title":"Example"})
        self.assertEqual(video.url, base + "22")
        self.assertEqual(video.caption, "Example")

    def test_no_merged_or_oversize(self):
        with self.assertRaises(MediaUnavailable):
            pick_youtube_video({"formats":[{"url":"https://rr.googlevideo.com/videoplayback?x=1","ext":"mp4", "vcodec":"avc1","acodec":"none","filesize":1_000_000}]})
        with self.assertRaises(MediaUnavailable):
            pick_youtube_video({"_type":"playlist","entries":[]})


if __name__ == "__main__":
    unittest.main()
