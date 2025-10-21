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
        self.host = os.getenv('SSH_HOST_ANOMALY_DETECTION')
        self.port = int(os.getenv('SSH_PORT_ANOMALY_DETECTION', 22)) # 默认端口为22
        self.username = os.getenv('SSH_USERNAME_ANOMALY_DETECTION')
        self.password = os.getenv('SSH_PASSWORD_ANOMALY_DETECTION')
        self.remote_base_path = os.getenv('SSH_REMOTE_BASE_PATH_ANOMALY_DETECTION').replace('\\', '/')
        self.remote_image_path = os.path.join(self.remote_base_path,'upload').replace('\\', '/')
        self.remote_result_dir_path = os.path.join(self.remote_base_path,'output',self.process_id).replace('\\', '/')
        self.conda_executable = os.getenv('CONDA_EXECUTABLE_ANOMALY_DETECTION')
        self.conda_env_name = os.getenv('CONDA_ENV_NAME_ANOMALY_DETECTION')
        self.local_download_dir = "download/anomaly_detection"

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

    def transfer_single_image_file(self, file_path: str) -> str:
        """
        将指定的单张图片文件传输到远程服务器，并以 process_id.{文件后缀} 进行保存。

        Args:
            file_path (str): 本地图片文件的完整路径。
        Returns:
            str: 成功上传后，远程文件的完整路径。如果传输失败，则返回 None。
        """
        if not os.path.isfile(file_path):
            logging.error(f"本地文件路径 {file_path} 无效或不是一个文件。")
            return None

        # 获取文件的后缀名
        file_extension = os.path.splitext(file_path)[-1]
        
        # 拼接远程文件的完整路径
        # 使用 os.path.join 确保路径拼接的正确性，然后替换为URL风格的斜杠'/'
        remote_file_name = f"{self.process_id}{file_extension}"
        remote_file_path = os.path.join(self.remote_image_path, remote_file_name).replace('\\', '/')
        logging.info(f"目标远程文件路径: {remote_file_path}")

        try:
            # 执行上传操作
            self.sftp.put(file_path, remote_file_path)
            logging.info(f"成功传输文件: {file_path} -> {remote_file_path}")
            
            return remote_file_path

        except Exception as e:
            # 如果在传输过程中发生任何其他错误（如连接断开、权限不足等）
            logging.error(f"文件传输过程中发生错误: {e}")
            return None
        
    def download_result(self,image_path:str) -> str:
        """
        从服务器下载结果文件
        Returns:
            str: 本地结果文件路径
        """
        # 本地下载地址
        local_result_dir = os.path.join(self.local_download_dir, self.process_id)
        local_result_pre_image = os.path.join(local_result_dir, 'prediction.png')
        local_result_heat_map = os.path.join(local_result_dir, 'heat_map.png')
        local_result_json = os.path.join(local_result_dir, 'result.json')

        # 如果没有这个文件夹，则创建
        if not os.path.exists(local_result_dir):
            os.makedirs(local_result_dir)

        # 拼接远程结果文件路径
        remote_result_pre_image = os.path.join(self.remote_result_dir_path, f"{self.process_id}.png").replace('\\', '/')
        remote_result_heat_map = os.path.join(self.remote_result_dir_path, f"{self.process_id}_heatmap.png").replace('\\', '/')
        remote_result_json = os.path.join(self.remote_result_dir_path, f"{self.process_id}.json").replace('\\', '/')
        

        logger.info(f"准备下载文件: {remote_result_pre_image} -> {local_result_pre_image}")
        logger.info(f"准备下载文件: {remote_result_heat_map} -> {local_result_heat_map}")
        logger.info(f"准备下载文件: {remote_result_json} -> {local_result_json}")
        try:
            # 下载结果可视化文件
            # 将原图复制到结果目录
            image_filename = os.path.basename(image_path)
            shutil.copy(image_path, os.path.join(local_result_dir, image_filename))
            logger.info(f"成功复制原图到结果目录: {os.path.join(local_result_dir, image_filename)}")

            self.sftp.get(remotepath=remote_result_pre_image, localpath=local_result_pre_image)
            self.sftp.get(remotepath=remote_result_heat_map, localpath=local_result_heat_map)
            self.sftp.get(remotepath=remote_result_json, localpath=local_result_json)
            logger.info(f"成功下载结果文件: {local_result_pre_image}")
            logger.info(f"成功下载结果文件: {local_result_heat_map}")
            logger.info(f"成功下载结果文件: {local_result_json}")

        except Exception as e:
            logger.error(f"下载结果失败: {e}")
            logger.error(f"远程文件路径: {remote_result_pre_image}")
            logger.error(f"远程文件路径: {remote_result_heat_map}")
            logger.error(f"远程文件路径: {remote_result_json}")
            logger.error(f"本地文件路径: {local_result_pre_image}")
            logger.error(f"本地文件路径: {local_result_heat_map}")
            logger.error(f"本地文件路径: {local_result_json}")
            raise e

        return local_result_pre_image, local_result_heat_map, local_result_json

    def process_images(self, image_path: str):
        """
        处理图片
        Args:
            image_path: 本地图片路径
        Returns:
            str: 本地结果文件路径
        """
        try:
            # 连接服务器
            self.connect()

            # 上传图片
            remote_target_dir = self.transfer_single_image_file(image_path)

            # 判断图片类型并选择相应的脚本
            image_type = self.image_type_judge(image_path)
            if image_type == "square":
                script_name = "api.py"
            elif image_type == "very long":
                script_name = "api_v2_http.py"
            else:
                script_name = "api_v3_http.py"
            logger.info(f"图片类型判断: {image_type}, 使用脚本: {script_name}")

            # 执行Python命令,首先进入工作目录并激活conda环境
            cmd = f'''bash -c 'cd {self.remote_base_path} && \
{self.conda_executable} run -n {self.conda_env_name} python3 {script_name} --file_path {remote_target_dir} --process_id {self.process_id}
' '''
            stdin, stdout, stderr = self.ssh.exec_command(cmd)
            
            # 获取输出
            result = stdout.read().decode().strip()
            error = stderr.read().decode().strip()
            
            logger.info(f"远程处理命令输出: {result}")
            if error:
                logger.warning(f"远程处理命令异常: {error}")
            
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
                local_result_pre_image, local_result_heat_map, local_result_json = self.download_result(image_path=image_path)
                
                return local_result_pre_image, local_result_heat_map, local_result_json
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
        start_time = time.time()
        
        while True:
            try:
                # 检查是否超时
                if time.time() - start_time > max_wait_time:
                    logger.error("等待处理完成超时")
                    return False
                    
                # 检查远程文件是否存在
                stdin, stdout, stderr = self.ssh.exec_command(f"ls {self.remote_result_dir_path}")
                if stderr.read().decode().strip():  # 如果有错误输出，说明文件不存在
                    logger.info("正在等待处理完成...")
                    time.sleep(3)  # 等待3秒后重试
                    continue
                return True  # 文件存在，返回成功
            except Exception as e:
                logger.error(f"检查远程文件时出错: {e}")
                time.sleep(3)
                continue

    def image_type_judge(self, image_path: str) -> str:
        """
        判断图片类型并返回对应的API脚本类型
        Args:
            image_path: 图片文件路径
        Returns:
            str: 图片类型标识 - "square"（方形）、"special"（特殊尺寸）、"other"（其他）
        """
        try:
            from PIL import Image
            with Image.open(image_path) as img:
                width, height = img.size
                
                # 判断是否为方形图片（宽高比接近1:1）
                ratio = width / height
                if 0.9 <= ratio <= 1.1:
                    image_type = "square"
                # 判断是否为特殊尺寸 31901x1000
                elif width == 31901 and height == 1000:
                    image_type = "very long"
                # 其他类型
                else:
                    image_type = "other"
                
                logger.info(f"图片尺寸: {width}x{height}, 图片类型: {image_type}")
                return image_type
        except Exception as e:
            logger.error(f"判断图片类型失败: {str(e)}")
            # 如果无法判断，默认使用 api_v3.py
            return "other"

    def get_process_id(self)->str:
        """
        获取处理ID
        Returns:
            str: 处理ID
        """
        return FileNamer.generate_time_based_name()

if __name__ == "__main__":
    ssh_client = SSHClient()
    local_result_pre_image, local_result_heat_map, local_result_json = ssh_client.process_images(image_path="C:/Users/Administrator/Desktop/项目/analysis_system/test/gsy_8.jpg")
    print(local_result_pre_image, local_result_heat_map, local_result_json)
