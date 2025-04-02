from flask import Flask, render_template, request, jsonify
from threading import Lock
import time
import psutil
from sandbox import Sandbox
import logging
from datetime import datetime

app = Flask(__name__)
app.logger.setLevel(logging.INFO)

# 全局状态存储
execution_history = []
system_stats = []
security_events = []
stats_lock = Lock()

# 默认沙箱配置
DEFAULT_CONFIG = {
    'cpu_time_limit': 10,
    'memory_limit': 128,
    'timeout': 30,
    'allow_network': False,
    'allow_filesystem': False,
    'use_docker': False
}

@app.route('/')
def index():
    return render_template('index.html', 
                         default_config=DEFAULT_CONFIG,
                         history=execution_history[-10:])

@app.route('/execute', methods=['POST'])
def execute_code():
    code = request.form.get('code', '')
    config = {
        'cpu_time_limit': int(request.form.get('cpu_time_limit', DEFAULT_CONFIG['cpu_time_limit'])),
        'memory_limit': int(request.form.get('memory_limit', DEFAULT_CONFIG['memory_limit'])),
        'timeout': int(request.form.get('timeout', DEFAULT_CONFIG['timeout'])),
        'allow_network': request.form.get('allow_network') == 'on',
        'allow_filesystem': request.form.get('allow_filesystem') == 'on',
        'use_docker': request.form.get('use_docker') == 'on'
    }
    
    sandbox = Sandbox(**config)
    start_time = time.time()
    status = "success"
    error = None
    result = None
    
    try:
        result = sandbox.execute(code)
    except Exception as e:
        status = "error"
        error = str(e)
        # log_security_event(f"Execution failed: {error}")
    
    execution_data = {
        'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'code': code[:100] + '...' if len(code) > 100 else code,
        'config': config,
        'status': status,
        'result': str(result)[:200] if result else None,
        'error': error,
        'duration': round(time.time() - start_time, 2)
    }
    
    with stats_lock:
        execution_history.append(execution_data)
    
    return jsonify({
        'status': status,
        'result': str(result) if result else None,
        'error': error
    })

@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

@app.route('/api/stats')
def get_stats():
    # 获取系统资源使用情况
    cpu_percent = psutil.cpu_percent()
    memory_info = psutil.virtual_memory()
    
    stats = {
        'timestamp': datetime.now().strftime("%H:%M:%S"),
        'cpu': cpu_percent,
        'memory': memory_info.percent,
        'memory_used': round(memory_info.used / (1024 * 1024), 1),
        'memory_total': round(memory_info.total / (1024 * 1024)),
        'security_events': security_events[-5:]
    }
    
    with stats_lock:
        system_stats.append(stats)
        # 保持最近100条记录
        if len(system_stats) > 100:
            system_stats.pop(0)
    
    return jsonify(stats)

def log_security_event(message):
    event = {
        'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'message': message
    }
    with stats_lock:
        security_events.append(event)
        # 保持最近50条安全事件
        if len(security_events) > 50:
            security_events.pop(0)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)