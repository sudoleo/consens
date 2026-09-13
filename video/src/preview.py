"""Local-only media preview with byte ranges for reliable video seeking."""
from http.server import ThreadingHTTPServer,SimpleHTTPRequestHandler
from pathlib import Path
import argparse,os,re
from runtime import OUT
class Handler(SimpleHTTPRequestHandler):
    def __init__(self,*args,**kwargs):super().__init__(*args,directory=str(OUT),**kwargs)
    def end_headers(self):
        self.send_header('Accept-Ranges','bytes')
        self.send_header('Cache-Control','no-cache')
        super().end_headers()
    def send_head(self):
        self.byte_range=None
        requested=self.headers.get('Range')
        file=Path(self.translate_path(self.path))
        if not requested or not file.is_file():return super().send_head()
        match=re.fullmatch(r'bytes=(\d*)-(\d*)',requested.strip())
        size=file.stat().st_size
        if not match or not any(match.groups()):self.send_error(416,'Invalid range');return None
        first,last=match.groups()
        start=int(first) if first else max(0,size-int(last))
        end=min(size-1,int(last)) if first and last else size-1
        if start<0 or start>end or start>=size:
            self.send_response(416);self.send_header('Content-Range',f'bytes */{size}');self.send_header('Content-Length','0');self.end_headers();return None
        try:stream=file.open('rb')
        except OSError:self.send_error(404,'File unavailable');return None
        stream.seek(start);self.byte_range=(start,end)
        self.send_response(206);self.send_header('Content-Type',self.guess_type(str(file)))
        self.send_header('Content-Range',f'bytes {start}-{end}/{size}')
        self.send_header('Content-Length',str(end-start+1));self.send_header('Last-Modified',self.date_time_string(os.fstat(stream.fileno()).st_mtime));self.end_headers();return stream
    def copyfile(self,source,output):
        if self.byte_range is None:return super().copyfile(source,output)
        remaining=self.byte_range[1]-self.byte_range[0]+1
        while remaining:
            block=source.read(min(65536,remaining))
            if not block:break
            output.write(block);remaining-=len(block)
    def log_message(self,fmt,*args):pass
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=8782);args=parser.parse_args()
    server=ThreadingHTTPServer(('127.0.0.1',args.port),Handler)
    print(f'Preview: http://127.0.0.1:{args.port}/',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()
