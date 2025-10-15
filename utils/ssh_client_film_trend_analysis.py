from utils.file_namer import FileNamer
from dotenv import load_dotenv
import os
import paramiko
import time
import logging
import shutil

logger = logging.getLogger(__name__)

class SSHClient:
    def __init__(self):
        # 加载环境变量
        load_dotenv()
        self.process_id = self.get_process_id()
        self.host = os.getenv('SSH_HOST_TREND_ANALYSIS')
        self.port = int(os.getenv('SSH_PORT_TREND_ANALYSIS', 22)) # 默认端口为22
        self.username = os.getenv('SSH_USERNAME_TREND_ANALYSIS')
        self.password = os.getenv('SSH_PASSWORD_TREND_ANALYSIS')
        self.remote_base_path = os.getenv('SSH_REMOTE_BASE_PATH_TREND_ANALYSIS').replace('\\', '/')
        self.remote_image_path = os.path.join(self.remote_base_path,'upload',self.process_id).replace('\\', '/')
        self.remote_result_dir_path = os.path.join(self.remote_base_path,'output',self.process_id).replace('\\', '/')
        self.conda_executable = os.getenv('CONDA_EXECUTABLE_TREND_ANALYSIS')
        self.conda_env_name = os.getenv('CONDA_ENV_NAME_TREND_ANALYSIS')
        self.local_download_dir = "download/trend_analysis"

    def connect(self):
        """建立SSH连接"""
        try:
            self.ssh = paramiko.SSHClient()
            self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # 添加超时设置
            self.ssh.connect(
                self.host,
                self.port,
                self.username,
                self.password,
                timeout=30,  # 连接超时30秒
                banner_timeout=30,  # 横幅超时30秒
                auth_timeout=30     # 认证超时30秒
            )
            self.sftp = self.ssh.open_sftp()
            logger.info("成功连接到服务器")
        except Exception as e:
            logger.error(f"连接服务器失败: {str(e)}")
            raise e
            
    
    def close(self):
        """关闭SSH连接"""
        try:
            if hasattr(self, 'sftp') and self.sftp:
                self.sftp.close()
                logger.info("SFTP连接已关闭")
                self.sftp = None  # 标记为已关闭
        except Exception as e:
            logger.error(f"关闭SFTP连接时出错: {str(e)}")
        
        try:
            if hasattr(self, 'ssh') and self.ssh:
                self.ssh.close()
                logger.info("SSH连接已关闭")
                self.ssh = None  # 标记为已关闭
        except Exception as e:
            logger.error(f"关闭SSH连接时出错: {str(e)}")

    def transfer_images_from_directory(self, dir_path: str) -> str:
        """
        将指定本地文件夹下的所有文件传输到远程服务器以process_id命名的子文件夹中。

        Args:
            dir_path (str): 本地存放图片的文件夹路径。
        Returns:
            str: 成功上传后，远程文件夹的完整路径。如果传输失败，则返回 None。
        """
        # 步骤 1: 拼接远程目标文件夹的完整路径
        # 使用 os.path.join 确保路径拼接的正确性，然后替换为URL风格的斜杠'/'
        remote_target_dir = os.path.join(self.remote_image_path).replace('\\', '/')
        logger.info(f"目标远程文件夹路径: {remote_target_dir}")

        try:
            # 步骤 2: 在远程服务器上创建以 process_id 命名的文件夹
            # 使用 try-except 块来处理文件夹已经存在的情况
            try:
                self.sftp.mkdir(remote_target_dir)
                logger.info(f"成功创建远程文件夹: {remote_target_dir}")
            except IOError as e:
                # 如果文件夹已存在，sftp.mkdir会抛出IOError异常，我们可以忽略它并继续
                logger.warning(f"创建远程文件夹失败: {remote_target_dir},错误信息: {e}")

            # 步骤 3: 遍历本地文件夹并将所有图片(文件)传输到远程文件夹
            logger.info(f"正在检查本地文件夹: {dir_path}")
            logger.info(f"文件夹是否存在: {os.path.exists(dir_path)}")
            logger.info(f"是否为目录: {os.path.isdir(dir_path)}")
            
            files_to_transfer = os.listdir(dir_path)
            if not files_to_transfer:
                logger.warning(f"本地文件夹 {dir_path} 为空，没有文件需要传输。")
                return remote_target_dir

            logger.info(f"在 {dir_path} 中找到 {len(files_to_transfer)} 个项目，准备开始传输...")

            transferred_count = 0
            for filename in files_to_transfer:
                local_file_path = os.path.join(dir_path, filename)
                
                # 确保我们只上传文件，跳过任何子文件夹
                if os.path.isfile(local_file_path):
                    remote_file_path = os.path.join(remote_target_dir, filename).replace('\\', '/')
                    
                    # 执行上传操作
                    self.sftp.put(local_file_path, remote_file_path)
                    transferred_count += 1
                    logger.info(f"  - 成功: {local_file_path} -> {remote_file_path}")
                else:
                    logger.warning(f"跳过子目录: {local_file_path}")

            logger.info(f"传输完成！共 {transferred_count} 个文件成功上传到 {remote_target_dir}")
            
            return remote_target_dir

        except Exception as e:
            # 如果在传输过程中发生任何其他错误（如连接断开、权限不足等）
            # 记录错误并返回 None
            logger.error(f"文件传输过程中发生错误: {e}")
            return None
        
    def download_result(self,dir_path:str) -> str:
        """
        从服务器下载结果文件
        Returns:
            str: 本地结果文件路径
        """
        # 本地下载地址
        local_result_dir = os.path.join(self.local_download_dir, self.process_id)
        local_result_file = os.path.join(local_result_dir, 'prediction.jpg')
        local_result_json = os.path.join(local_result_dir, f"{self.process_id}.json")

        # 如果没有这个文件夹，则创建
        if not os.path.exists(local_result_dir):
            os.makedirs(local_result_dir)

        # 拼接远程结果文件路径
        remote_result = os.path.join(self.remote_result_dir_path, "prediction.jpg").replace('\\', '/')
        remote_result_json = os.path.join(self.remote_result_dir_path, f"{self.process_id}.json").replace('\\', '/')

        logger.info(f"准备下载文件: {remote_result} -> {local_result_file}")
        logger.info(f"准备下载文件: {remote_result_json} -> {local_result_json}")

        # 下载结果可视化文件
        try:
            # 复制原图文件夹到结果目录
            shutil.copytree(dir_path, os.path.join(local_result_dir, 'original_images'), dirs_exist_ok=True)
            logger.info(f"成功复制原图文件夹到结果目录: {os.path.join(local_result_dir, 'original_images')}")
            self.sftp.get(remotepath=remote_result, localpath=local_result_file)
            self.sftp.get(remotepath=remote_result_json, localpath=local_result_json)
            logger.info(f"成功下载结果文件: {local_result_file}")
            logger.info(f"成功下载结果文件: {local_result_json}")

        except Exception as e:
            logger.error(f"下载结果失败: {e}")
            logger.error(f"远程文件路径: {remote_result}")
            logger.error(f"远程文件路径: {remote_result_json}")
            logger.error(f"本地文件路径: {local_result_file}")
            logger.error(f"本地文件路径: {local_result_json}")
            raise e

        return local_result_file, local_result_json

    def process_images(self, dir_path: str):
        """
        处理图片
        Args:
            dir_path: 图片文件夹路径
        Returns:
            str: 本地结果文件路径
        """
        try:
            # 连接服务器
            self.connect()

            # 上传图片
            remote_target_dir = self.transfer_images_from_directory(dir_path)

            # 执行Python命令,首先进入工作目录并激活conda环境
            cmd = f'''bash -c 'cd {self.remote_base_path} && \
{self.conda_executable} run -n {self.conda_env_name} python3 api.py --folder_path {remote_target_dir} --process_id {self.process_id}
' '''
            stdin, stdout, stderr = self.ssh.exec_command(cmd)
            
            # 获取输出
            result = stdout.read().decode().strip()
            error = stderr.read().decode().strip()
            
            logger.info(f"远程处理命令输出: {result}")
            if error:
                logger.warning(f"远程处理命令错误: {error}")
            
            # 检查命令执行状态
            exit_status = stdout.channel.recv_exit_status()
            if exit_status != 0:
                logger.error(f"远程处理命令执行失败，退出状态: {exit_status}")
                raise Exception(f"远程处理失败，退出状态: {exit_status}")
                
            # 等待处理完成
            if not self.wait_for_processing_complete():
                self.close()
                raise Exception("处理超时")
            else:
                # 下载结果文件
                pred_file_path, local_result_json = self.download_result(dir_path=dir_path)
                
                return pred_file_path, local_result_json
        except Exception as e:
            logger.error(f"处理过程中出现错误: {e}")
            raise e
        finally:
            self.close()

    def wait_for_processing_complete(self,max_wait_time: int = 60) -> bool:
        """
        等待远程处理完成
        Args:
            max_wait_time: 最大等待时间（秒）
        Returns:
            bool: 是否处理完成
        """
        # 构建完整的远程结果文件路径
        remote_result_dir = os.path.join(self.remote_result_dir_path).replace('\\', '/')
        remote_result_file = os.path.join(remote_result_dir, "prediction.jpg").replace('\\', '/')
        
        start_time = time.time()
        
        while True:
            try:
                # 检查是否超时
                if time.time() - start_time > max_wait_time:
                    logger.error("等待处理完成超时")
                    return False
                    
                # 检查远程结果文件是否存在
                stdin, stdout, stderr = self.ssh.exec_command(f"test -f {remote_result_file} && echo 'exists' || echo 'not_exists'")
                result = stdout.read().decode().strip()
                error = stderr.read().decode().strip()
                
                if error:
                    logger.error(f"检查远程文件时出错: {error}")
                    time.sleep(3)
                    continue
                    
                if result == 'exists':
                    logger.info(f"远程结果文件已生成: {remote_result_file}")
                    return True
                else:
                    logger.info("正在等待处理完成...")
                    time.sleep(3)  # 等待3秒后重试
                    continue
                    
            except Exception as e:
                logger.error(f"检查远程文件时出错: {e}")
                time.sleep(3)
                continue

    def get_process_id(self)->str:
        """
        获取处理ID
        Returns:
            str: 处理ID
        """
        return FileNamer.generate_time_based_name()

if __name__ == "__main__":
    ssh_client = SSHClient()
    pred_file_path, local_result_json = ssh_client.process_images(dir_path="C:/Users/Administrator/Desktop/项目/analysis_system/test")
    print(pred_file_path, local_result_json)
    pred_file_path, pred_level = ssh_client.process_images(dir_path="C:/Users/Administrator/Desktop/项目/analysis_system/test")
    print(pred_file_path, pred_level)
