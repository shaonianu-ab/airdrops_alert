import requests

class msg_handler:

    WEIXIN_POST_ENDPOINT = {  # 改为类变量
        'url': '',
        'headers': {
            'Content-Type': 'application/json',
        }
    }

    @classmethod
    def send_to_wx(cls, msg):
        print(msg)
        requests.post(
            cls.WEIXIN_POST_ENDPOINT['url'],
            json={"msgtype": "text", "text": {"content": msg}},
            headers=cls.WEIXIN_POST_ENDPOINT['headers']
        )
    
    @classmethod
    def other_notify(cls, msg):
        print(msg)
        pass

# msg_handler.send_to_wx('hello world')