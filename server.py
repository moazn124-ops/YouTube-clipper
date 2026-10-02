from flask import Flask, request, jsonify, send_file, render_template_string
import yt_dlp
import os
import uuid
import subprocess

app = Flask(__name__)

BASE = '/tmp/ytclip'
os.makedirs(BASE, exist_ok=True)

BGUTIL_SERVER_HOME = '/opt/bgutil-ytdlp-pot-provider/server'

HTML = '''<!doctype html>
<html lang="ar" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>قاصّ يوتيوب</title>

<style>
body{
    margin:0;
    background:#0b0b0f;
    color:#fff;
    font-family:Arial,sans-serif
}
.wrap{
    max-width:760px;
    margin:40px auto;
    padding:24px
}
.card{
    background:#17171d;
    border:1px solid #2a2a33;
    border-radius:18px;
    padding:24px;
    box-shadow:0 10px 35px #0006
}
h1{margin-top:0}
.muted{color:#aaa}
input,select,button{
    width:100%;
    box-sizing:border-box;
    padding:14px;
    margin:8px 0;
    border-radius:10px;
    border:1px solid #383842;
    background:#101016;
    color:#fff;
    font-size:16px
}
button{
    background:#e11;
    color:white;
    border:0;
    font-weight:bold;
    cursor:pointer
}
button:disabled{opacity:.5}
.grid{
    display:grid;
    grid-template-columns:1fr 1fr;
    gap:12px
}
.status{
    margin-top:15px;
    padding:12px;
    border-radius:10px;
    background:#101016;
    white-space:pre-wrap
}
.download{
    display:block;
    text-align:center;
    background:#19a463;
    color:#fff;
    padding:14px;
    border-radius:10px;
    text-decoration:none;
    margin-top:12px
}
.small{
    font-size:13px;
    color:#999
}
@media(max-width:600px){
    .wrap{
        margin:10px auto;
        padding:12px
    }
    .grid{
        grid-template-columns:1fr
    }
}
</style>
</head>

<body>

<div class="wrap">
<div class="card">

<h1>✂️ قاصّ فيديوهات يوتيوب</h1>

<p class="muted">
ضع رابط الفيديو، حدّد الجزء المطلوب، ثم اختر الجودة.
</p>

<input
    id="url"
    placeholder="https://www.youtube.com/watch?v=..."
>

<button id="info">
جلب معلومات الفيديو
</button>

<div id="details"></div>

<div id="controls" style="display:none">

<div class="grid">

<div>
<label>من</label>
<input id="start" value="0">
</div>

<div>
<label>إلى</label>
<input id="end" value="10">
</div>

</div>

<label>الجودة</label>

<select id="quality"></select>

<button id="cut">
قص الفيديو وتجهيزه
</button>

</div>

<div
    id="status"
    class="status"
    style="display:none"
></div>

<a
    id="download"
    class="download"
    style="display:none"
>
⬇️ تحميل المقطع
</a>

</div>
</div>

<script>

const $ = x => document.getElementById(x);

function fmt(s){
    s = Math.round(s || 0);

    return String(Math.floor(s / 3600)).padStart(2,'0')
        + ':'
        + String(Math.floor(s % 3600 / 60)).padStart(2,'0')
        + ':'
        + String(s % 60).padStart(2,'0');
}

function esc(s){
    return (s || '').replace(
        /[&<>"']/g,
        m => ({
            '&':'&amp;',
            '<':'&lt;',
            '>':'&gt;',
            '"':'&quot;',
            "'":'&#39;'
        }[m])
    );
}

$('info').onclick = async () => {

    $('status').style.display = 'block';
    $('status').textContent = 'جارٍ جلب المعلومات...';
    $('details').innerHTML = '';

    try {

        let r = await fetch('/info', {
            method:'POST',
            headers:{
                'Content-Type':'application/json'
            },
            body:JSON.stringify({
                url:$('url').value
            })
        });

        let d = await r.json();

        if(!r.ok)
            throw Error(d.error);

        $('details').innerHTML =
            '<p><b>' +
            esc(d.title) +
            '</b><br>' +
            '<span class="small">المدة: ' +
            fmt(d.duration) +
            '</span></p>';

        $('quality').innerHTML =
            d.qualities.map(q =>
                `<option value="${q.height}">
                    ${q.height}p
                </option>`
            ).join('');

        $('end').value =
            Math.min(10,d.duration);

        $('controls').style.display='block';
        $('status').style.display='none';

    } catch(e){

        $('status').textContent =
            'خطأ: ' + e.message;
    }
};

$('cut').onclick = async () => {

    $('cut').disabled = true;

    $('status').style.display='block';
    $('status').textContent =
        'جارٍ القص والمعالجة...';

    $('download').style.display='none';

    try {

        let r = await fetch('/cut', {
            method:'POST',
            headers:{
                'Content-Type':'application/json'
            },
            body:JSON.stringify({
                url:$('url').value,
                start:$('start').value,
                end:$('end').value,
                height:$('quality').value
            })
        });

        let d = await r.json();

        if(!r.ok)
            throw Error(d.error);

        $('status').textContent =
            'تم تجهيز المقطع.';

        $('download').href = d.download;
        $('download').style.display='block';

    } catch(e){

        $('status').textContent =
            'خطأ: ' + e.message;

    } finally {

        $('cut').disabled = false;
    }
};

</script>

</body>
</html>
'''

def parse_time(x):

    x = str(x).strip()

    if ':' in x:

        p = x.split(':')

        if len(p) == 2:
            return int(p[0]) * 60 + float(p[1])

        if len(p) == 3:
            return (
                int(p[0]) * 3600
                + int(p[1]) * 60
                + float(p[2])
            )

    return float(x)


def clean_url(u):
    return u.strip()


def ytdlp_common():

    return {
        'quiet': True,
        'no_warnings': True,

        'extractor_args': {
            'youtube': {
                'player_client': [
                    'mweb',
                    'tv',
                    'web_safari'
                ]
            },

            'youtubepot-bgutilscript': {
                'server_home': [
                    BGUTIL_SERVER_HOME
                ]
            }
        }
    }


@app.get('/')
def home():
    return render_template_string(HTML)


@app.get('/healthz')
def healthz():
    return 'ok', 200


@app.post('/info')
def info():

    data = request.json or {}

    u = clean_url(data.get('url',''))

    if not u:
        return jsonify(
            error='ضع رابط يوتيوب أولًا'
        ),400

    try:

        opts = ytdlp_common()

        opts.update({
            'skip_download': True
        })

        with yt_dlp.YoutubeDL(opts) as y:

            d = y.extract_info(
                u,
                download=False
            )

        qs = {}

        for f in d.get('formats', []):

            h = f.get('height')
            v = f.get('vcodec')

            if h and v != 'none':
                qs[h] = True

        heights = sorted(
            qs,
            key=lambda x:int(x)
        )

        return jsonify(
            title=d.get('title',''),
            duration=d.get('duration') or 0,
            qualities=[
                {
                    'height':h,
                    'note':'فيديو + صوت'
                }
                for h in heights
            ]
        )

    except Exception as e:

        return jsonify(
            error=str(e)
        ),400


@app.post('/cut')
def cut():

    data = request.json or {}

    u = clean_url(data.get('url',''))

    try:
        h = int(data.get('height',720))
        start = parse_time(
            data.get('start',0)
        )
        end = parse_time(
            data.get('end',0)
        )

    except Exception:
        return jsonify(
            error='الوقت أو الجودة غير صحيحة'
        ),400

    if not u:
        return jsonify(
            error='ضع رابط يوتيوب أولًا'
        ),400

    if start < 0 or end <= start:
        return jsonify(
            error='وقت النهاية يجب أن يكون أكبر من البداية'
        ),400

    job = str(uuid.uuid4())

    out = os.path.join(
        BASE,
        job + '.mp4'
    )

    template = os.path.join(
        BASE,
        job + '.%(ext)s'
    )

    try:

        opts = ytdlp_common()

        opts.update({

            'format':
                f'bestvideo[height<={h}]'
                '+bestaudio/'
                f'best[height<={h}]',

            'outtmpl':template,

            'merge_output_format':'mp4',

            'noplaylist':True
        })

        with yt_dlp.YoutubeDL(opts) as y:

            y.download([u])

        src = next(
            (
                os.path.join(BASE,x)

                for x in os.listdir(BASE)

                if x.startswith(job + '.')
                and not x.endswith('.part')
                and x != os.path.basename(out)
            ),
            None
        )

        if not src:
            return jsonify(
                error='تعذر تنزيل الفيديو'
            ),500

        subprocess.run(
            [
                'ffmpeg',
                '-y',
                '-ss',
                str(start),
                '-i',
                src,
                '-t',
                str(end-start),
                '-c',
                'copy',
                '-movflags',
                '+faststart',
                out
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

        try:
            os.remove(src)
        except:
            pass

        return jsonify(
            download='/download/' + job
        )

    except Exception as e:

        return jsonify(
            error='فشل القص: ' + str(e)
        ),500


@app.get('/download/<job>')
def download(job):

    p = os.path.join(
        BASE,
        job + '.mp4'
    )

    if not os.path.exists(p):

        return (
            'انتهت صلاحية الملف أو غير موجود',
            404
        )

    return send_file(
        p,
        as_attachment=True,
        download_name='youtube_clip.mp4',
        mimetype='video/mp4'
    )


if __name__ == '__main__':

    app.run(
        host='0.0.0.0',
        port=int(
            os.environ.get(
                'PORT',
                '10000'
            )
        )
    )
