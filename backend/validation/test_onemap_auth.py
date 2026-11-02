"""Expiry, cache, retry and secret-handling checks without live credentials."""
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from onemap_auth import OneMapTokens, TokenError
from onemap_adapter import Coordinate, OneMapClient


def response(token='fresh-test-token',expiry=2000):
    r=MagicMock()
    r.__enter__.return_value.read.return_value=json.dumps({'access_token':token,'expiry_timestamp':expiry}).encode()
    return r


class RenewalTests(unittest.TestCase):
    def test_valid_token_is_reused_then_renewed_before_expiry(self):
        manager=OneMapTokens('fixture@example.test','private-test-password')
        with patch('onemap_auth.time.time',return_value=1000), \
             patch('onemap_auth.urlopen',return_value=response()) as call:
            self.assertEqual(manager.get(),'fresh-test-token')
            self.assertEqual(manager.get(),'fresh-test-token')
            self.assertEqual(call.call_count,1)
        with patch('onemap_auth.time.time',return_value=1950), \
             patch('onemap_auth.urlopen',return_value=response('replacement',3000)) as call:
            self.assertEqual(manager.get(),'replacement')
            self.assertEqual(call.call_count,1)
        self.assertNotIn('private-test-password',repr(manager))
        self.assertNotIn('replacement',repr(manager))

    def test_concurrent_requests_share_one_renewal(self):
        manager=OneMapTokens('fixture@example.test','private-test-password')
        with patch('onemap_auth.time.time',return_value=1000), \
             patch('onemap_auth.urlopen',return_value=response()) as call:
            with ThreadPoolExecutor(max_workers=5) as pool:
                values=list(pool.map(lambda _:manager.get(),range(10)))
            self.assertEqual(values,['fresh-test-token']*10)
            self.assertEqual(call.call_count,1)

    def test_bad_auth_body_does_not_become_a_cached_token(self):
        for payload in [{'access_token':'bad token','expiry_timestamp':2000},
                        {'access_token':'test','expiry_timestamp':1001},{'error':'private-test-password'},{}]:
            manager=OneMapTokens('fixture@example.test','private-test-password')
            r=MagicMock()
            r.__enter__.return_value.read.return_value=json.dumps(payload).encode()
            with self.subTest(payload=payload),patch('onemap_auth.time.time',return_value=1000), \
                 patch('onemap_auth.urlopen',return_value=r):
                with self.assertRaises(TokenError) as caught:
                    manager.get()
                self.assertNotIn('private-test-password',str(caught.exception))
                self.assertEqual(manager._token,'')

    def test_auth_failure_is_safe_and_does_not_loop(self):
        manager=OneMapTokens('fixture@example.test','private-test-password')
        error=HTTPError('https://example.test',401,'private-test-password',{},BytesIO(b'private-test-password'))
        with patch('onemap_auth.urlopen',side_effect=error) as call:
            with self.assertRaisesRegex(TokenError,'^authentication_failed$'):
                manager.get()
            self.assertEqual(call.call_count,1)

    def test_rejected_access_token_retries_route_exactly_once(self):
        manager=MagicMock()
        manager.get.side_effect=['expired-test-token','replacement-test-token']
        client=OneMapClient('managed-token',tokens=manager)
        with patch.object(client,'_request_once',side_effect=[
                ('authentication_failed',None,None),('authentication_failed',None,None)]) as request:
            result=client.route(Coordinate(1.3,103.8),Coordinate(1.31,103.81),'drive')
        self.assertEqual(result.status,'authentication_failed')
        self.assertEqual(request.call_count,2)
        self.assertEqual(manager.get.call_args.kwargs,{'rejected_token':'expired-test-token'})


if __name__=='__main__':
    unittest.main()
