import math
from ultralytics.models import YOLO
from werkzeug.utils import secure_filename, send_from_directory
import os
import uuid
import cv2
from flask import Response, jsonify
import time
import json
from datetime import datetime
import mysql.connector
from flask import Flask, render_template, request, redirect, url_for, flash, session
import pymysql

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # 用于session加密



def get_db_connection():
    return pymysql.connect(
        host='localhost',
        user='root',
        password='dwx20031120.',
        database='brain_tumor_detection',
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor
    )


app = Flask(__name__)
app.secret_key = 'very_secret_key_123456'  # 建议换成更复杂一点的，防止被猜到

# 连接数据库
db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="dwx20031120.",
    database="brain_tumor_detection"
)
cursor = db.cursor()
# 注册页面


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']

        password = request.form['password']


        # 创建数据库连接
        cursor = mysql.connection.cursor()

        # 检查用户名是否已存在
        cursor.execute('SELECT * FROM users WHERE username = %s', (username,))
        user = cursor.fetchone()

        if user:
            flash('用户名已存在，请选择其他用户名！')
            return redirect(url_for('register'))

        # 插入新用户数据
        cursor.execute('INSERT INTO users (username, password) VALUES (%s, %s)',
                       (username, password))
        mysql.connection.commit()
        cursor.close()

        flash('注册成功！请登录！')
        return redirect(url_for('login'))

    return render_template('register.html')


# 登录页面
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # 创建数据库连接
        cursor = mysql.connection.cursor()

        # 获取用户数据
        cursor.execute('SELECT * FROM users WHERE username = %s', (username,))
        user = cursor.fetchone()

        if user and user[2] == password:  # user[2] 是密码字段
            # 登录成功，将用户信息存入 session

            session['username'] = user[1]  # user[1] 是用户名
            return render_template('index.html')  # 主页

        else:
            flash('用户名或密码错误！')
            return redirect(url_for('login'))  # 如果认证失败，重定向回登录页面

    return render_template('login.html')


# 主页路由
@app.route('/')
def index():
    if 'username' not in session:
        return redirect(url_for('login'))  # 如果未登录，重定向到登录页面
    return render_template('index.html', active_page='home') # 加载主页模板

# 注销
@app.route('/logout')
def logout():
    session.clear()  # 清除 session 数据
    return redirect(url_for('login'))  # 注销后返回登录页面

# 设置全局变量存储最新更新时间
last_update_time = datetime.min  # 初始时间设置为一个很久以前的时间

# SSE 路由 - 用于实时推送数据
@app.route('/statistics/stream')
def stream_statistics():
    def generate():
        global last_update_time

        def get_current_statistics():
            cursor.execute("SELECT result, COUNT(*) as count FROM image_records GROUP BY result")
            image_data = cursor.fetchall()
            image_results = [{'result': row[0] if row[0] else '未知', 'count': row[1]} for row in image_data]

            cursor.execute("SELECT result, COUNT(*) as count FROM video_records GROUP BY result")
            video_data = cursor.fetchall()
            video_results = [{'result': row[0] if row[0] else '未知', 'count': row[1]} for row in video_data]

            cursor.execute("""
                SELECT model, COUNT(*) as count FROM (
                    SELECT model FROM image_records
                    UNION ALL
                    SELECT model FROM video_records
                ) as all_models
                GROUP BY model
            """)
            model_data = cursor.fetchall()
            model_usage = [{'model': row[0] if row[0] else '未知', 'count': row[1]} for row in model_data]

            return {'image_results': image_results, 'video_results': video_results, 'model_usage': model_usage}

        # 第一次直接推送一次
        initial_data = get_current_statistics()
        yield f"data: {json.dumps(initial_data)}\n\n"

        while True:
            # 每隔一段时间检查数据库是否有更新
            cursor.execute("SELECT MAX(timestamp) FROM video_records")
            latest_video_time = cursor.fetchone()[0]
            cursor.execute("SELECT MAX(timestamp) FROM image_records")
            latest_image_time = cursor.fetchone()[0]

            latest_time = max(latest_video_time, latest_image_time)

            if latest_time > last_update_time:
                last_update_time = latest_time

                updated_data = get_current_statistics()
                yield f"data: {json.dumps(updated_data)}\n\n"

            time.sleep(5)

    return Response(generate(), mimetype='text/event-stream')




# # 首页
# @app.route('/')
# def index():
#     return render_template('index.html', active_page='home')

label_map = {
    'glioma': '神经胶质瘤',
    'meningioma': '脑膜瘤',
    'no_tumor': '无肿瘤',
    'pituitary': '垂体',
    # 如果有更多标签继续加
}

# MySQL 配置
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'dwx20031120.'
app.config['MYSQL_DB'] = 'brain_tumor_detection'

# 图片检测配置
UPLOAD_FOLDER_img = 'static/uploads/image_upload'
RESULT_FOLDER_img = 'static/results/image_result'
MODEL_FOLDER = 'models/'
ALLOWED_EXTENSIONS_img = {'png', 'jpg', 'jpeg'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER_img
app.config['RESULT_FOLDER'] = RESULT_FOLDER_img
os.makedirs(RESULT_FOLDER_img, exist_ok=True)
os.makedirs(RESULT_FOLDER_img, exist_ok=True)


# 视频检测配置
UPLOAD_FOLDER_video = 'static/uploads/videos_upload'
RESULT_FOLDER_video = 'static/results/videos_result'
FRAME_FOLDER = os.path.join(RESULT_FOLDER_video, 'frames')
MODEL_FOLDER = 'models/'
ALLOWED_EXTENSIONS_video = {'mp4', 'avi', 'mov'}
os.makedirs(UPLOAD_FOLDER_video, exist_ok=True)
os.makedirs(FRAME_FOLDER, exist_ok=True)

# 数据库配置
db = pymysql.connect(host='localhost', user='root', password='dwx20031120.', database='brain_tumor_detection', charset='utf8mb4')
cursor = db.cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS video_results (
    id INT AUTO_INCREMENT PRIMARY KEY,
    video_name VARCHAR(255),
    frame_path TEXT,
    confidence FLOAT,
    detected_at DATETIME
)
""")
db.commit()


# 初始化 MySQL
from flask_mysqldb import MySQL
mysql = MySQL(app)



# 工具函数
def allowed_file(filename, allowed_extensions):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions

def get_model_list():
    return [f for f in os.listdir(MODEL_FOLDER) if f.endswith('.pt')]

def save_record(record):
    cur = mysql.connection.cursor()
    cur.execute('''
        INSERT INTO image_records (id, image_path, result, probability, timestamp,model) 
        VALUES (%s, %s, %s, %s, %s,%s)
    ''', (record['id'], record['image'], str(record['result']), record['probability'], record['time'], record['model']))
    mysql.connection.commit()
    cur.close()


# 获取可用模型列表
def get_model_list():
    return [f for f in os.listdir(MODEL_FOLDER) if f.endswith('.pt')]

# 图像检测页面
@app.route('/image_detect')
def image_detect():
    return render_template('image_detect.html', models=get_model_list(), active_page='image_detect')

# 图像识别接口
@app.route('/detect', methods=['POST'])
def detect():
    images = request.files.getlist('images')
    model_name = request.form.get('model')
    model_path = os.path.join(MODEL_FOLDER, model_name)

    if not images or not model_name or not os.path.exists(model_path):
        return jsonify({'error': '模型或图像未正确上传'}), 400

    model = YOLO(model_path)

    results_list = []
    label_counter = {}
    detected_images = 0
    for img in images:
        if img or not allowed_file(img, ALLOWED_EXTENSIONS_img):
            filename = secure_filename(str(uuid.uuid4()) + '_' + img.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            print(filepath)
            img.save(filepath)

            results = model(filepath)[0]
            result_img_path = os.path.join(app.config['RESULT_FOLDER'], 'res_' + filename)
            results.save(filename=result_img_path)

            labels = list({label_map[model.names[int(box.cls)]] for box in results.boxes}) if results.boxes else []
            for label in labels:
                label_counter[label] = label_counter.get(label, 0) + 1
            if labels:
                detected_images += 1

            result_info = {
                'original': '/' + filepath.replace('\\', '/'),
                'result': '/' + result_img_path.replace('\\', '/'),
                'labels': labels
            }

            results_list.append(result_info)

            # 保存单条记录到数据库
            record = {
                'id': str(uuid.uuid4())[:8],
                'image': '/' + filepath.replace('\\', '/'),
                'result': labels,
                'probability': str(round(max([float(box.conf) for box in results.boxes], default=0) * 100, 2)) + '%',
                'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'model':str(model_name)
            }
            save_record(record)

    return jsonify({
        'results': results_list,
        'summary': {
            'total_images': len(images),
            'detected_images': detected_images,
            'labels': label_counter
        }
    })


# 图片记录页面
@app.route('/image_record')
def image_record():
    page = request.args.get('page', 1, type=int)
    per_page = 10
    offset = (page - 1) * per_page

    search = request.args.get('search', '').strip()

    cur = mysql.connection.cursor()

    # 构建条件查询语句
    base_query = 'SELECT * FROM image_records'
    count_query = 'SELECT COUNT(*) FROM image_records'
    conditions = []
    params = []

    if search:
        conditions.append('result LIKE %s')
        params.append(f"%{search}%")

    if conditions:
        where_clause = ' WHERE ' + ' AND '.join(conditions)
        base_query += where_clause
        count_query += where_clause

    base_query += ' ORDER BY timestamp DESC LIMIT %s OFFSET %s'
    params.extend([per_page, offset])

    # 获取总记录数
    cur.execute(count_query, params[:-2])
    total_records = cur.fetchone()[0]

    # 获取当前页数据
    cur.execute(base_query, params)
    records = cur.fetchall()
    cur.close()

    total_pages = (total_records + per_page - 1) // per_page

    return render_template('image_record.html',
                           records=records,
                           page=page,
                           total_pages=total_pages,
                           search=search,
                           active_page='image_record')

# 删除图片
@app.route('/delete_image_record/<string:id>', methods=['POST'])
def delete_image_record(id):
    try:
        print(f"尝试删除记录ID: {id}")  # 打印日志，确认接收到的 ID
        cur = mysql.connection.cursor()
        cur.execute('DELETE FROM brain_tumor_detection.image_records WHERE id = %s', (id,))
        mysql.connection.commit()
        cur.close()
        print("记录删除成功")
        return jsonify({'success': True})
    except Exception as e:
        print(f"删除记录时出错: {str(e)}")  # 打印错误信息
        return jsonify({'error': '删除失败', 'message': str(e)}), 500

# 视频检测页面
@app.route('/video_detect')
def video_detect():
    return render_template('video_detect.html', models=get_model_list(), active_page='video_detect')

@app.route('/video_detect/upload', methods=['POST'])
def video_detect_upload():
    if 'video' not in request.files:
        return jsonify({'error': '未上传视频'}), 400

    video = request.files['video']
    threshold = float(request.form.get('threshold', 0.5))
    model_name = request.form.get('model_path')

    if not model_name or not os.path.exists(os.path.join(MODEL_FOLDER, model_name)):
        return jsonify({'error': '无效的模型路径'}), 400

    if video.filename == '' or not allowed_file(video.filename, ALLOWED_EXTENSIONS_video):
        return jsonify({'error': '无效的视频文件'}), 400

    filename = secure_filename(str(uuid.uuid4()) + '_' + video.filename)
    video_path = os.path.join(UPLOAD_FOLDER_video, filename)
    video.save(video_path)

    model_path = os.path.join(MODEL_FOLDER, model_name)
    model = YOLO(model_path)

    cap = cv2.VideoCapture(video_path)
    frame_count = 0
    tumor_frame_count = 0
    max_conf = 0
    tumor_sizes = []
    saved_frames = []
    detected_labels = set()

    # 先插入空白记录，获取record_id
    try:
        cursor.execute("""
            INSERT INTO video_records (video_path, upload_time, duration, result, confidence, model, detected_labels)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (filename, datetime.now(), 0, '', 0, model_name, ''))
        db.commit()
        record_id = cursor.lastrowid
    except Exception as e:
        print(f"数据库插入失败: {e}")
        db.rollback()
        return jsonify({'error': '数据库插入失败'}), 500

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            frame_count += 1

            temp_image_path = os.path.join(FRAME_FOLDER, f"frame_{uuid.uuid4()}.jpg")
            cv2.imwrite(temp_image_path, frame)

            results = model(temp_image_path)[0]

            if results.boxes:
                confs = [float(box.conf) for box in results.boxes if float(box.conf) >= threshold]

                if confs:
                    tumor_frame_count += 1
                    max_conf = sum(confs) / len(confs) if confs else 0

                    unique_name = f"frame_{record_id}_{uuid.uuid4()}.jpg"
                    save_path = os.path.join("static/results/videos_result/frames_result", unique_name)
                    results.save(filename=save_path)
                    saved_frames.append(save_path)

                    for box in results.boxes:
                        if float(box.conf) >= threshold:
                            label = model.names[int(box.cls)]
                            if label in label_map:
                                detected_labels.add(label_map[label])

                    for box in results.boxes:
                        if float(box.conf) >= threshold:
                            x1, y1, x2, y2 = box.xyxy[0].tolist()
                            width = abs(x2 - x1)
                            height = abs(y2 - y1)
                            tumor_sizes.append((width, height))

            os.remove(temp_image_path)

    finally:
        cap.release()

    avg_width = sum(w for w, _ in tumor_sizes) / len(tumor_sizes) if tumor_sizes else 0
    avg_height = sum(h for _, h in tumor_sizes) / len(tumor_sizes) if tumor_sizes else 0

    result_label = ', '.join(detected_labels) if detected_labels else '未知'

    # 更新数据库，写入检测结果和统计信息
    try:
        import json
        frames_json = json.dumps(saved_frames)

        cursor.execute("""
            UPDATE video_records
            SET duration=%s, result=%s, confidence=%s, detected_labels=%s, frames_json=%s
            WHERE id=%s
        """, (frame_count, result_label, max_conf, result_label, frames_json, record_id))
        db.commit()
    except Exception as e:
        print(f"数据库更新失败: {e}")
        db.rollback()

    return jsonify({
        'tumor_frame_count': tumor_frame_count,
        'total_frames': frame_count,
        'max_confidence': round(max_conf * 100, 2),
        'avg_size': {
            'width': round(avg_width, 1),
            'height': round(avg_height, 1)
        },
        'video_path': '/' + video_path.replace('\\', '/'),
        'frames': ['/' + f.replace('\\', '/') for f in saved_frames],
        'detection_summary': result_label
    })




# 获取视频记录
@app.route('/video_record')
def video_record():
    page = int(request.args.get('page', 1))
    per_page = 10
    offset = (page - 1) * per_page

    cur = mysql.connection.cursor()

    # 获取总记录数
    cur.execute('SELECT COUNT(*) FROM video_records')
    total = cur.fetchone()[0]
    total_pages = (total + per_page - 1) // per_page

    # 获取当前页的数据
    cur.execute('SELECT * FROM video_records ORDER BY timestamp DESC LIMIT %s OFFSET %s', (per_page, offset))
    records = cur.fetchall()
    cur.close()

    return render_template(
        'video_record.html',
        records=records,
        page=page,
        total_pages=total_pages
    )



@app.route('/video_record/detail/<int:record_id>')
def video_record_detail(record_id):
    try:
        cursor.execute("SELECT * FROM video_records WHERE id = %s", (record_id,))
        record = cursor.fetchone()

        if not record:
            return "记录未找到", 404

        # 获取存储帧图片路径的 JSON 字符串
        cursor.execute("SELECT frames_json FROM video_records WHERE id = %s", (record_id,))
        frames_row = cursor.fetchone()
        frames = []
        if frames_row and frames_row[0]:
            import json
            frames_raw = json.loads(frames_row[0])

            # 处理路径，统一转换为 /static/ 开头的web访问路径，去除前面多余部分
            frames = []
            for f in frames_raw:
                # 假设f路径类似 static\results\videos_result\frames_result\frame_xxx.jpg
                # 转换反斜杠为斜杠
                f = f.replace('\\', '/')
                # 找到 static 开始的位置，截取后面的路径
                idx = f.find('static/')
                if idx != -1:
                    f = '/' + f[idx:]  # 变成 /static/...
                else:
                    # 如果没有static，直接加前缀/static/
                    f = '/static/' + f
                frames.append(f)

        return render_template('video_record_detail.html', record=record, frames=frames)

    except Exception as e:
        print(f"查询记录出错: {e}")
        return "服务器错误", 500


# 删除视频记录
@app.route('/delete_video_record/<int:id>', methods=['POST'])
def delete_video_record(id):
    try:
        cur = mysql.connection.cursor()
        # 删除视频记录
        cur.execute('DELETE FROM video_records WHERE id = %s', (id,))
        mysql.connection.commit()
        cur.close()
        return jsonify({'success': True})
    except Exception as e:
        print(f"删除记录时出错: {str(e)}")
        return jsonify({'error': '删除失败', 'message': str(e)}), 500


def get_db_connection():
    return pymysql.connect(
        host='localhost',
        user='root',
        password='dwx20031120.',
        database='brain_tumor_detection',
        charset='utf8mb4',
        cursorclass=pymysql.cursors.Cursor  # 注意这里用普通 Cursor
    )
# 用户管理页面
@app.route('/user_manage')
def user_manage():
    # 获取当前页码（默认第1页）
    page = request.args.get('page', default=1, type=int)
    per_page = 10  # 每页显示10个用户
    offset = (page - 1) * per_page

    db = get_db_connection()
    cursor = db.cursor()

    # 查询总用户数
    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]
    total_pages = math.ceil(total_users / per_page)

    # 查询当前页的用户数据
    cursor.execute("""
        SELECT id, username, role, email, created_at, status 
        FROM users 
        ORDER BY created_at DESC 
        LIMIT %s OFFSET %s
    """, (per_page, offset))
    users = cursor.fetchall()

    # 处理 created_at 字段（如果是字符串，转为 datetime）
    processed_users = []
    for user in users:
        user = list(user)
        if isinstance(user[4], str):
            try:
                user[4] = datetime.strptime(user[4], "%Y-%m-%d %H:%M:%S")
            except:
                pass
        processed_users.append(user)

    db.close()
    return render_template(
        'user_manage.html',
        users=processed_users,
        page=page,
        total_pages=total_pages
    )
# 添加新用户（接收AJAX post请求）
@app.route('/add_user', methods=['POST'])
def add_user():
    username = request.form.get('username')
    email = request.form.get('email')
    password = request.form.get('password')
    role = request.form.get('role')

    if not (username and email and password and role):
        return jsonify({'success': False, 'message': '缺少必要信息'})

    cur = mysql.connection.cursor()
    cur.execute("INSERT INTO users (username, password, email, role, status, created_at) VALUES (%s, %s, %s, %s, %s, %s)",
                (username, password, email, role, 'active', datetime.now()))
    mysql.connection.commit()
    cur.close()

    return jsonify({'success': True})

# 禁用用户
@app.route('/disable_user/<int:user_id>', methods=['POST'])
def disable_user(user_id):
    cur = mysql.connection.cursor()
    cur.execute("UPDATE users SET status = 'inactive' WHERE id = %s", (user_id,))
    mysql.connection.commit()5
    cur.close()
    return jsonify({'success': True})

# 编辑用户（可选）
@app.route('/edit_user/<int:user_id>', methods=['POST'])
def edit_user(user_id):
    username = request.form.get('username')
    email = request.form.get('email')
    role = request.form.get('role')
    phone=request.form.get('phone')
    cur = mysql.connection.cursor()
    cur.execute("UPDATE users SET username = %s, email = %s, phone=%s,role = %s WHERE id = %s",
                (username, email, phone, role, user_id))
    mysql.connection.commit()
    cur.close()
    return jsonify({'success': True})

@app.route('/user_profile', methods=['GET', 'POST'])
def user_profile():
    if 'username' not in session:
        return redirect(url_for('login'))

    cursor = mysql.connection.cursor()

    # 查询当前用户信息
    cursor.execute('SELECT username, email, phone,role FROM users WHERE username = %s', (session['username'],))
    user = cursor.fetchone()  # user[0]=username, user[1]=email, user[2]=role

    if request.method == 'POST':
        new_email = request.form.get('email')
        cursor.execute('UPDATE users SET email = %s WHERE username = %s', (new_email, session['username']))
        mysql.connection.commit()
        flash('信息更新成功！')
        return redirect(url_for('user_profile'))

    # 传给模板
    return render_template('user_profile.html', username=user[0], email=user[1], phone=user[2],role=user[3])


# 头像上传文件夹
UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

@app.route('/upload_avatar', methods=['POST'])
def upload_avatar():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    file = request.files['avatar']
    if file and file.filename != '':
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        avatar_url = '/' + filepath  # 保存的是相对路径，方便前端显示

        # 更新用户头像
        cursor = mysql.connection.cursor()
        cursor.execute('UPDATE users SET avatar_url = %s WHERE id = %s', (avatar_url, session['user_id']))
        mysql.connection.commit()
        cursor.close()

        flash('头像上传成功！')

    else:
        flash('请选择要上传的图片！')

    return redirect(url_for('user_profile'))

# 修改密码接口
@app.route('/change_password', methods=['POST'])
def change_password():
    if 'username' not in session:
        return redirect(url_for('login'))

    current_password = request.form.get('currentPassword')
    new_password = request.form.get('newPassword')
    confirm_password = request.form.get('confirmPassword')

    if new_password != confirm_password:
        flash('两次输入的新密码不一致！')
        return redirect(url_for('user_profile'))

    cursor = mysql.connection.cursor()
    cursor.execute('SELECT password FROM users WHERE username = %s', (session['username'],))
    user = cursor.fetchone()

    if user and user[0] == current_password:  # 注意：这里没用 hash，如果用 hash，需要用 check_password_hash
        # 更新密码
        cursor.execute('UPDATE users SET password = %s WHERE username = %s', (new_password, session['username']))
        mysql.connection.commit()
        flash('密码修改成功，请重新登录！')
        session.clear()
        return redirect(url_for('login'))
    else:
        flash('当前密码错误！')
        return redirect(url_for('user_profile'))

@app.route('/update_profile', methods=['POST'])
def update_profile():
    if 'username' not in session:
        return redirect(url_for('login'))

    email = request.form['email']
    phone = request.form['phone']

    cursor = mysql.connection.cursor()
    cursor.execute('UPDATE users SET email = %s, phone = %s WHERE username = %s', (email, phone, session['username']))
    mysql.connection.commit()
    cursor.close()

    flash('个人信息更新成功！')
    return redirect(url_for('user_profile'))


# 静态文件路由
@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory(app.config['STATIC_FOLDER'], filename)


@app.route('/uploads/<path:filename>')
def upload_files(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


if __name__ == '__main__':
    app.run(debug=True)