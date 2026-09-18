import http.client
import json
import os
from http.server import HTTPServer
from threading import Thread
import unittest
from unittest.mock import patch

from api.webhook import handler, process_update
from clipjet import Video

class HandlerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server=HTTPServer(('127.0.0.1', 0), handler)
        cls.worker=Thread(target=cls.server.serve_forever, daemon=True)
        cls.worker.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.worker.join(timeout=2)

    def request(self, method='POST', secret='TEST_SECRET_123456789', data=b'{}'):
        conn=http.client.HTTPConnection('127.0.0.1', self.server.server_port,timeout=2)
        conn.request(method,'/api/webhook',body=data,headers={'X-Telegram-Bot-Api-Secret-Token':secret,'Content-Type':'application/json'})
        response=conn.getresponse()
        status=response.status
        body=json.loads(response.read())
        conn.close()
        return status, body

    def test_secret_required(self):
        with patch.dict(os.environ, {'BOT_TOKEN':'nonreal','WEBHOOK_SECRET':'TEST_SECRET_123456789'}):
            self.assertEqual(self.request(secret='wrong')[0],403)
            self.assertEqual(self.request(secret='TEST_SECRET_123456789')[0],200)
            self.assertEqual(self.request(method='GET')[1]['status'],'ready')

    def test_unconfigured(self):
        with patch.dict(os.environ, {'BOT_TOKEN':'','WEBHOOK_SECRET':''}):
            self.assertEqual(self.request()[0],503)

    def test_malformed_json(self):
        with patch.dict(os.environ, {'BOT_TOKEN':'nonreal','WEBHOOK_SECRET':'TEST_SECRET_123456789'}):
            self.assertEqual(self.request(data=b'nope')[0],400)

    def test_empty_text_without_network(self):
        update={'update_id':10001,'message':{'chat':{'type':'private','id':234},'from':{'id':234},'text':''}}
        with patch.dict(os.environ, {'BOT_OWNER_ID':'234'}), patch('api.webhook.telegram_call') as send:
            process_update(update, 'nonreal')
            self.assertEqual(send.call_args.args[1], 'sendMessage')

    def test_video_flow_without_network(self):
        update={'update_id':43219999,'message':{'chat':{'type':'private','id':123},'from':{'id':123},'text':'https://x.com/user/status/123456789'}}
        calls=[]
        def fake_call(token,method,payload,timeout=12):
            calls.append((method,payload))
            return {'ok':True}
        with patch.dict(os.environ, {'BOT_OWNER_ID':'123'}), \
             patch('api.webhook.telegram_call', side_effect=fake_call), \
             patch('api.webhook.resolve_x_video', return_value=Video('https://video.twimg.com/a.mp4','Clip')):
            process_update(update,'nonreal')
            process_update(update,'nonreal')
        self.assertEqual([a[0] for a in calls],['sendMessage','sendVideo'])
        self.assertEqual(calls[-1][1]['video'],'https://video.twimg.com/a.mp4')

if __name__=='__main__':
    unittest.main()
