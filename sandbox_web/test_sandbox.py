import unittest
import time,os
from sandbox import Sandbox, SandboxError, ResourceLimitExceeded, SecurityViolation,sandboxed

class TestSandbox(unittest.TestCase):
    def setUp(self):
        self.sandbox = Sandbox(
            cpu_time_limit=1,
            memory_limit=50,  # 50MB
            timeout=2,
            allow_network=False,
            allow_filesystem=False
        )
    
    def test_safe_code(self):
        """测试安全代码执行"""
        result = self.sandbox.execute("x = 1 + 2; _ = x * 3")
        self.assertEqual(result, 9)
    
    def test_timeout(self):
        """测试执行超时"""
        with self.assertRaises(ResourceLimitExceeded):
            self.sandbox.execute("while True: pass")
    
    def test_memory_limit(self):
        """测试内存限制"""
        with self.assertRaises(ResourceLimitExceeded):
            self.sandbox.execute("_ = bytearray(100 * 1024 * 1024)")  # 100MB
    
    def test_security_violation(self):
        """测试安全违规检测"""
        # 测试禁止的导入
        with self.assertRaises(SecurityViolation):
            self.sandbox.execute("import os")
            
        # 测试禁止的函数
        with self.assertRaises(SecurityViolation):
            self.sandbox.execute("open('test.txt', 'w')")
    
    def test_network_restriction(self):
        """测试网络限制"""
        with self.assertRaises(SecurityViolation):
            self.sandbox.execute("import requests; requests.get('http://example.com')")
    
    def test_filesystem_restriction(self):
        """测试文件系统限制"""
        with self.assertRaises(SecurityViolation):
            self.sandbox.execute("with open('test.txt', 'w') as f: f.write('test')")
    
    def test_allowed_filesystem(self):
        """测试允许文件系统访问的情况"""
        sandbox = Sandbox(allow_filesystem=True, allowed_paths=['/tmp'])
        try:
            sandbox.execute("with open('/tmp/sandbox_test.txt', 'w') as f: f.write('test')")
        except SecurityViolation:
            self.fail("Should allow filesystem access when configured")
    
    def test_decorator(self):
        """测试沙箱装饰器"""
        @sandboxed(cpu_time_limit=1, memory_limit=50, timeout=2)
        def add(a, b):
            return a + b
            
        result = add(2, 3)
        self.assertEqual(result, 5)
        
        with self.assertRaises(RuntimeError):
            @sandboxed(cpu_time_limit=1)
            def infinite_loop():
                while True: pass
                
            infinite_loop()

class TestDockerSandbox(unittest.TestCase):
    @unittest.skipUnless(os.getenv('TEST_DOCKER'), "Docker tests disabled by default")
    def test_docker_execution(self):
        """测试Docker容器执行"""
        sandbox = Sandbox(use_docker=True)
        result = sandbox.execute("_ = 2 + 2")
        self.assertEqual(result.strip(), "4")

if __name__ == '__main__':
    unittest.main()