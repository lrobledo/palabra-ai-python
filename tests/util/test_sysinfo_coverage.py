import pytest
from unittest.mock import patch, MagicMock
from palabra_ai.util.sysinfo import SystemInfo


class TestSysinfoAdditionalCoverage:
    def test_collect_resource_limits_exception(self):
        """Test resource limits collection with exceptions"""
        with patch('resource.getrlimit', side_effect=ValueError("Test error")):
            info = SystemInfo()
            # Should complete without raising
            assert info.resource_limits == {}

    def test_collect_locale_exception(self):
        """Test locale collection with exception"""
        with patch('locale.getdefaultlocale', side_effect=Exception("Test error")):
            info = SystemInfo()
            # Should have empty locale_info
            assert info.locale_info == {}

    def test_collect_user_info_no_pwd(self):
        """Test user info collection when pwd module fails"""
        with patch('pwd.getpwuid', side_effect=Exception("No pwd")):
            with patch('os.getuid', return_value=1000):
                with patch('os.getgid', return_value=1000):
                    with patch('os.getlogin', return_value="testuser"):
                        info = SystemInfo()
                        assert info.user_info['uid'] == 1000
                        assert info.user_info['gid'] == 1000
                        assert info.user_info['username'] == "testuser"

    def test_collect_user_info_all_fail(self):
        """Test user info when all methods fail"""
        with patch('pwd.getpwuid', side_effect=Exception("No pwd")):
            with patch('os.getuid', side_effect=AttributeError("No getuid")):
                with patch('os.getgid', side_effect=AttributeError("No getgid")):
                    with patch('os.getlogin', side_effect=Exception("No login")):
                        info = SystemInfo()
                        # Should handle all exceptions gracefully

    def test_collect_python_paths_exception(self):
        """Test Python paths collection with exception"""
        with patch('sysconfig.get_path', side_effect=Exception("Path error")):
            info = SystemInfo()
            # Should have empty python_paths
            assert info.python_paths == {}
