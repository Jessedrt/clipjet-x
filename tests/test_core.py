import unittest
from clipjet import InvalidLink, MediaUnavailable, canonical_x_post, pick_video, verified_media_url

class UrlTests(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(canonical_x_post('https://twitter.com/ClipJet/status/123456789?s=20'), 'https://x.com/ClipJet/status/123456789')
        self.assertEqual(canonical_x_post('https://x.com/i/web/status/12345678'), 'https://x.com/i/status/12345678')

    def test_bad_urls(self):
        bad = [
            'http://x.com/joe/status/12345678', 'https://x.com.evil.org/joe/status/12345678',
            'https://notx.com/joe/status/12345678', 'https://x.com@evil.org/joe/status/12345678',
            'https://x.com:8080/joe/status/12345678', 'https://x.com/joe',
            'https://x.com/joe/status/nan', 'https://x.com/joe/status/12345678#part',
            'https://x.com/joe/status/12345678 https://x.com/joe/status/98765432',
            'https://x.com/joe/status/12345678/redirect', 'https://x.com/aaaaaaaaaaaaaaaa/status/12345678',
        ]
        for url in bad:
            with self.subTest(url=url), self.assertRaises(InvalidLink):
                canonical_x_post(url)

    def test_media_url(self):
        self.assertTrue(verified_media_url('https://video.twimg.com/ext_tw_video/abc/video.mp4?tag=1'))
        for url in ('http://video.twimg.com/a.mp4', 'https://video.twimg.com.evil.org/a.mp4',
                    'https://video.twimg.com/playlist.m3u8', 'https://user@video.twimg.com/a.mp4',
                    'https://video.twimg.com:999/a.mp4'):
            with self.subTest(url=url):
                self.assertFalse(verified_media_url(url))

class FormatTests(unittest.TestCase):
    def test_select_best_under_limit(self):
        formats = [
            {'url':'https://video.twimg.com/v/360.mp4', 'height':360, 'filesize':4_000_000},
            {'url':'https://video.twimg.com/v/720.mp4', 'height':720, 'filesize':13_000_000},
            {'url':'https://video.twimg.com/v/1080.mp4', 'height':1080, 'filesize':19_000_000},
            {'url':'https://video.twimg.com/v/hls.m3u8', 'height':1080},
            {'url':'https://evil.com/v/720.mp4', 'height':720, 'filesize':1_000_000},
            {'url':'https://video.twimg.com/v/mute.mp4', 'height':720, 'acodec':'none', 'filesize':1_000_000},
        ]
        result=pick_video({'formats':formats, 'title':'Example'})
        self.assertEqual(result.url, 'https://video.twimg.com/v/720.mp4')
        self.assertEqual(result.caption, 'Example')

    def test_unknown_size_prefers_small(self):
        data={'formats':[
            {'url':'https://video.twimg.com/x/720.mp4','height':720},
            {'url':'https://video.twimg.com/x/360.mp4','height':360},
        ]}
        self.assertTrue(pick_video(data).url.endswith('360.mp4'))

    def test_oversize_and_invalid(self):
        with self.assertRaises(MediaUnavailable):
            pick_video({'formats':[{'url':'https://video.twimg.com/a.mp4','filesize':20_000_000}]})
        with self.assertRaises(MediaUnavailable):
            pick_video({})

if __name__=='__main__':
    unittest.main()
