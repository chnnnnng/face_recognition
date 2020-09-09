from flask import Flask, request, redirect, abort
from util.auth import authorize
from util.redis import redis
from util.response import response
from util.knn import train,predict
import face_recognition
import os
import math
from sklearn import neighbors
import pickle
from face_recognition.face_recognition_cli import image_files_in_folder
from time import perf_counter
import json

app = Flask(__name__,static_folder="./photos") #static_folder设置了静态文件的位置

#是否使用SECRET_KEY进行安全检测
app.config['USE_SECRET_KEY'] = False
#SECRET_KEY
app.config['SECRET_KEY'] = 'this_is_a_secret_key'
#照片上传目录
app.config['UPLOAD_FOLDER'] = 'photos/'
#每个人脸最多上传照片数量
app.config['MAX_UPLOAD_EACH_FACE'] = 5
#redis host
app.config['REDIS_HOST'] = 'localhost'
#redis port
app.config['REDIS_PORT'] = 6379
#redis password
app.config['REDIS_PASSWORD'] = ''
#redis key 前缀
app.config['REDIS_PREFIX'] = 'FRS:'
#允许上传的类型
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}

#开启redis
#如果使用python3 face.py 的方式运行，务必注释此行
redis = redis(app.config['REDIS_HOST'],app.config['REDIS_PORT'],app.config['REDIS_PASSWORD'],app.config['REDIS_PREFIX'])

#中间件 安全检测
@app.before_request
def process():
    #如果开启安全检测
    #检测规则：
    #将GET参数和POST参数以及SECRET_KET合并为一个数组，生序排列，合并成字符串（无分隔符），MD5加密，
    #将加密后的字符串作为token添加到headers中
    #如果验证失败 返回404
    if app.config['USE_SECRET_KEY']:
        gets = list(dict(request.args).values())
        posts = list(dict(request.form).values())
        token = request.headers['token']
        if not authorize(gets,posts,token,app.config['SECRET_KEY']):
            abort(404)


#注册人脸
#POST
#参数：faceid 必须 要保证唯一性 作为每一个人脸的唯一编号
#     photos  可选 要上传的照片
@app.route('/register', methods=['POST'])
def register():
    faceid = request.form['faceid']
    if _add_faceid(faceid): #faceid能否注册
        if 'photos' in request.files: #是否上传了照片
            for photo in request.files.getlist('photos'): #遍历照片
                if _is_upto_limit(faceid):
                    break
                _save_photo(faceid,photo)
            return response().succeed().message("FaceID("+str(faceid)+")注册成功,添加了"+\
                str(redis.getPicNum(faceid))+"/"+str(app.config['MAX_UPLOAD_EACH_FACE'])+\
                    "张照片").setdata(_set_b_2_list_str(redis.getPics(faceid))).make()
        return response().succeed().message("该FaceId可以注册").make()
    return response().error().message("该FaceId无法注册").make()


#添加人脸
#POST
#参数：faceid 必须
#     photos  必须
@app.route('/upload', methods=['POST'])
def upload():
    faceid = request.form['faceid']
    if not _add_faceid(faceid): #faceid是否已注册
        if 'photos' in request.files: #是否上传了照片
            for photo in request.files.getlist('photos'): #遍历照片
                if _is_upto_limit(faceid):
                    break
                _save_photo(faceid,photo)
            return response().succeed().message("FaceID("+str(faceid)+"),添加成功，现有"+\
                str(redis.getPicNum(faceid))+"/"+str(app.config['MAX_UPLOAD_EACH_FACE'])+\
                    "张照片").setdata(_set_b_2_list_str(redis.getPics(faceid))).make()
        return response().succeed().message("请上传照片").make()
    return response().error().message("该FaceId尚未注册").make()


#查询人脸照片
#GET
#参数：faceid 必须
@app.route('/photos', methods=['GET'])
def get_photos():
    faceid = request.args['faceid']
    if _add_faceid(faceid):
        return response().error().message("该FaceId尚未注册").make()
    return response().succeed().message("FaceID("+str(faceid)+"),共有"+\
                str(redis.getPicNum(faceid))+"/"+str(app.config['MAX_UPLOAD_EACH_FACE'])+\
                    "张照片").setdata(_set_b_2_list_str(redis.getPics(faceid))).make()


#查看某一张照片
#GET
#参数：faceid 必须
#     filename 必须
@app.route('/photo', methods=['GET'])
def get_photo():
    faceid = request.args['faceid']
    filename = request.args['filename']
    return app.send_static_file(str(faceid)+'/'+str(filename))


#删除指定照片
#POST
#参数：faceid 必须
#     filename list 必须
@app.route('/del_photos', methods=['POST'])
def del_photos():
    faceid = request.form['faceid']
    if _add_faceid(faceid):
        return response().error().message("该FaceId尚未注册").make()
    filename_str = request.form['filenames']
    filenames = json.loads(filename_str)
    for filename in filenames:
        os.remove(_get_directory(faceid,filename))
        redis.delPic(faceid,filename)
    return response().succeed().message("删除成功，FaceID("+str(faceid)+"),现有"+\
                str(redis.getPicNum(faceid))+"/"+str(app.config['MAX_UPLOAD_EACH_FACE'])+\
                    "张照片").setdata(_set_b_2_list_str(redis.getPics(faceid))).make()


#删除指定Face
#POST
#参数：faceid 必须
@app.route('/del_face', methods=['POST'])
def del_face():
    faceid = request.form['faceid']
    if _add_faceid(faceid):
        return response().error().message("该FaceId尚未注册").make()
    filenames = _set_b_2_list_str(redis.getPics(faceid))
    for filename in filenames:
        os.remove(_get_directory(faceid,filename))
    os.rmdir(_get_directory(faceid))
    redis.delFace(faceid)
    return response().succeed().message("删除成功，Face("+str(faceid)+")").make()


#训练模型
#GET
#参数：无
@app.route('/train', methods=['GET'])
def train_modal():
    try:
        print("Training KNN classifier...")
        start = perf_counter()
        train(app.config['UPLOAD_FOLDER'],model_save_path="trained_knn_model.clf")
        elapsed = (perf_counter() - start)
        print("Training complete!","time spend:",elapsed)
        return response().succeed().message("训练完毕！耗时："+str(elapsed)+"秒").make()
    except:
        return response().error().message("训练失败").make()


#识别
#POST
#参数：photo 必须
@app.route('/recognize', methods=['POST'])
def recognize():
    if 'photo' not in request.files:
        return response().error().message("未上传").make()
    photo = request.files['photo']
    if photo and _is_allowed_file(photo.filename):
        if _is_human_face(photo):
            start = perf_counter()
            resl = predict(photo, model_path="trained_knn_model.clf")
            elapsed = (perf_counter() - start)
            return response().succeed().message("识别完毕！FaceId:"+resl[0][0]+"。耗时："+str(elapsed)+"秒").setdata(resl).make()
    return response().error().message("识别失败").make()


#注册人脸Demo
@app.route('/demo/register', methods=['GET'])
def demo_register():
    return '''
        <!doctype html>
        <title>注册人脸DEMO</title>
        <h1>注册人脸DEMO</h1>
        <form method="POST" enctype="multipart/form-data" action="/register">
        <input type="file" name="photos" multiple>
        <input name="faceid">
        <input type="submit" value="Upload">
        </form>
    '''

#添加人脸Demo
@app.route('/demo/upload', methods=['GET'])
def demo_upload():
    return '''
        <!doctype html>
        <title>添加人脸DEMO</title>
        <h1>添加人脸DEMO</h1>
        <form method="POST" enctype="multipart/form-data" action="/upload">
        <input type="file" name="photos" multiple>
        <input name="faceid">
        <input type="submit" value="Upload">
        </form>
    '''

#人脸识别Demo
@app.route('/demo', methods=['GET'])
def demo_recognize():
    return '''
        <!doctype html>
        <title>人脸识别DEMO</title>
        <h1>人脸识别DEMO</h1>
        <form method="POST" enctype="multipart/form-data" action="/recognize">
        <input type="file" name="photo">
        <input type="submit" value="Upload">
        </form>
    '''


#异常捕捉
@app.errorhandler(404)
def error404(error):
    return response().error().message("未知错误").make()
@app.errorhandler(500)
def error500(error):
    return response().error().message("未知错误").make()
@app.errorhandler(400)
def error400(error):
    return response().error().message("未知错误").make()    


#内部使用，注册人脸
def _add_faceid(faceid):
    return redis.addFace(faceid)

#内部使用，检测文件类型是否允许
def _is_allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

#内部使用，保存一张图片
def _save_photo(faceid, photo):
    if photo and _is_allowed_file(photo.filename):
        print("allowed")
        if _is_human_face(photo):
            print("is human")
            _check_directory(faceid)
            photo.seek(0)
            photo.save(_get_directory(faceid,photo.filename))
            photo.close()
            return redis.addPic(faceid,photo.filename)
    return False    

#内部使用，检测照片中是否有且仅有一张人脸
def _is_human_face(photo):
    return len(face_recognition.face_locations(face_recognition.load_image_file(photo))) == 1

#内部使用，检测照片数量是否超过(达到)上限
def _is_upto_limit(faceid):
    return redis.getPicNum(faceid) >= app.config['MAX_UPLOAD_EACH_FACE']

#内部使用，检测目录是否存在，不存在则创建
def _check_directory(faceid):
    if not os.path.exists(_get_directory(faceid)):
        os.mkdir(_get_directory(faceid))

#内部使用，拼接目录路径
def _get_directory(faceid,filename=''):
    if filename == '':
        return app.config['UPLOAD_FOLDER']+str(faceid)
    else:
        return os.path.join(app.config['UPLOAD_FOLDER']+str(faceid)+'/'+str(filename))

#内部使用，set<byte> => list<string>
def _set_b_2_list_str(set):
    t = []
    for x in set:
        t.append(x.decode())
    return t

if __name__ == "__main__":
    redis = redis(app.config['REDIS_HOST'],app.config['REDIS_PORT'],app.config['REDIS_PASSWORD'],app.config['REDIS_PREFIX'])
    app.run(host='0.0.0.0', port=88, debug=False)
