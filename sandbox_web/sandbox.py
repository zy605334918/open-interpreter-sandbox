import ast
import resource
import sys
import time
import signal
import logging
import os
from typing import Dict, Any, Optional, List
import docker  # 可选Docker支持
from functools import wraps
import inspect  # 添加这行

class SandboxError(Exception):
    """沙箱执行异常基类"""
    pass

class ResourceLimitExceeded(SandboxError):
    """资源限制异常"""
    pass

class SecurityViolation(SandboxError):
    """安全违规异常"""
    pass

class Sandbox:
    def __init__(self, 
                 cpu_time_limit: int = 10, 
                 memory_limit: int = 128,  # MB
                 timeout: int = 30, 
                 allow_network: bool = False,
                 allow_filesystem: bool = False,
                 allowed_paths: List[str] = None,
                 use_docker: bool = False):
        """
        初始化沙箱环境
        
        参数:
            cpu_time_limit: CPU时间限制(秒)
            memory_limit: 内存限制(MB)
            timeout: 执行超时时间(秒)
            allow_network: 是否允许网络访问
            allow_filesystem: 是否允许文件系统访问
            allowed_paths: 允许访问的文件路径列表
            use_docker: 是否使用Docker容器
        """
        self.cpu_time_limit = cpu_time_limit
        self.memory_limit = memory_limit * 1024 * 1024  # 转换为字节
        self.timeout = timeout
        self.allow_network = allow_network
        self.allow_filesystem = allow_filesystem
        self.allowed_paths = allowed_paths or []
        self.use_docker = use_docker
        self.logger = self._setup_logger()
        
        if self.use_docker:
            self.docker_client = docker.from_env()
        
        # 设置资源限制
        self._set_resource_limits()
        
    def _setup_logger(self) -> logging.Logger:
        """设置安全日志记录器"""
        logger = logging.getLogger('code_sandbox')
        logger.setLevel(logging.INFO)
        
        handler = logging.FileHandler('sandbox.log')
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        
        return logger
    
    def _set_resource_limits(self):
        """设置系统资源限制"""
        try:
            # CPU时间限制(软限制和硬限制)
            resource.setrlimit(resource.RLIMIT_CPU, 
                             (self.cpu_time_limit, self.cpu_time_limit))
            
            # 内存限制
            resource.setrlimit(resource.RLIMIT_AS, 
                             (self.memory_limit, self.memory_limit))
            
            # 防止生成核心转储
            resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        except (resource.error, ValueError) as e:
            self.logger.warning(f"Failed to set resource limits: {e}")
    
    def _check_code_security(self, code: str):
        """通过AST分析检查代码安全性"""
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            raise SecurityViolation(f"Syntax error: {e}")
        
        # 禁止的模块和函数
        forbidden_imports = {
            'os', 'sys', 'subprocess', 'shutil', 'socket', 
            'requests', 'urllib', 'multiprocessing', 'ctypes'
        }
        
        forbidden_functions = {
            'open', 'exec', 'eval', 'input', 
            'compile', 'system', 'popen', 'spawn'
        }
        
        class SecurityVisitor(ast.NodeVisitor):
            def __init__(self, sandbox):
                self.sandbox = sandbox
                self.violations = []
            
            def visit_Import(self, node):
                for alias in node.names:
                    if alias.name in forbidden_imports:
                        self.violations.append(f"Forbidden import: {alias.name}")
                self.generic_visit(node)
                
            def visit_ImportFrom(self, node):
                if node.module in forbidden_imports:
                    self.violations.append(f"Forbidden import from: {node.module}")
                self.generic_visit(node)
                
            def visit_Call(self, node):
                if isinstance(node.func, ast.Name):
                    if node.func.id in forbidden_functions:
                        self.violations.append(f"Forbidden function call: {node.func.id}")
                self.generic_visit(node)
        
        visitor = SecurityVisitor(self)
        visitor.visit(tree)
        
        if visitor.violations:
            violations = "\n".join(visitor.violations)
            self.logger.warning(f"Security violations detected:\n{violations}")
            raise SecurityViolation(f"Code contains security violations:\n{violations}")
    
    def _run_in_docker(self, code: str) -> Any:
        """在Docker容器中执行代码"""
        try:
            container = self.docker_client.containers.run(
                'python:3.9-slim',
                command=['python', '-c', code],
                mem_limit=f'{self.memory_limit // (1024 * 1024)}m',
                cpu_period=100000,
                cpu_quota=int(100000 * self.cpu_time_limit),
                network_mode='none' if not self.allow_network else 'default',
                read_only=True,
                volumes={path: {'bind': path, 'mode': 'ro'} for path in self.allowed_paths},
                detach=True
            )
            
            try:
                result = container.wait(timeout=self.timeout)
                if result['StatusCode'] != 0:
                    logs = container.logs().decode('utf-8')
                    raise SandboxError(f"Docker execution failed: {logs}")
                
                output = container.logs().decode('utf-8')
                return output
            finally:
                container.remove(force=True)
                
        except docker.errors.DockerException as e:
            raise SandboxError(f"Docker execution error: {e}")
    
    def execute(self, code: str) -> Any:
        """
        在沙箱中执行代码
        
        参数:
            code: 要执行的Python代码
            
        返回:
            代码执行结果
            
        异常:
            如果执行违反安全规则或超过资源限制，抛出SandboxError
        """
        self.logger.info(f"Executing code:\n{code}")
        start_time = time.time()
        
        # 安全检查
        if not self.allow_network or not self.allow_filesystem:
            self._check_code_security(code)
        
        # 设置执行超时
        def timeout_handler(signum, frame):
            raise ResourceLimitExceeded(f"Execution timed out after {self.timeout} seconds")
        
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(self.timeout)
        
        try:
            # 限制全局命名空间
            safe_globals = {
                '__builtins__': {
                    k: v for k, v in __builtins__.items() 
                    if k not in ['open', 'exec', 'eval', 'input', 'compile']
                }
            }
            safe_locals = {}
            
            if self.use_docker:
                result = self._run_in_docker(code)
            else:
                # 执行代码
                exec(code, safe_globals, safe_locals)
                
                # 获取执行结果
                result = safe_locals.get('_', None)  # 获取最后一个表达式的值
            
            execution_time = time.time() - start_time
            self.logger.info(f"Code executed successfully in {execution_time:.2f}s")
            
            return result
            
        except ResourceLimitExceeded as e:
            self.logger.warning(f"Resource limit exceeded: {e}")
            raise
        except SecurityViolation as e:
            self.logger.warning(f"Security violation: {e}")
            raise
        except Exception as e:
            self.logger.error(f"Execution error: {e}")
            raise SandboxError(f"Execution failed: {e}")
        finally:
            signal.alarm(0)  # 取消超时

def sandboxed(**config):
    """装饰器函数，用于以沙箱模式执行函数"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            sandbox = Sandbox(**config)
            try:
                # 获取函数签名
                sig = inspect.signature(func)
                # 将函数调用转换为代码字符串
                func_code = f"""
def _sandboxed_func{sig}:
    return func(*args, **kwargs)
                
result = _sandboxed_func(*{args!r}, **{kwargs!r})
                """
                return sandbox.execute(func_code)
            except SandboxError as e:
                raise RuntimeError(f"Sandboxed execution failed: {e}")
        return wrapper
    return decorator