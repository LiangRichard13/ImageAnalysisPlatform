import datetime
import uuid
import hashlib

class FileNamer:
    @staticmethod
    def generate_time_based_name(format_type='default', prefix='', suffix=''):
        """
        生成基于时间的唯一文件夹名称

        Args:
            format_type (str): 命名格式类型
                - 'default': YYYYMMDD_HHMMSS_随机字符
                - 'compact': YYMMDDHHMMSS_随机字符
                - 'readable': YYYY-MM-DD_HH-MM-SS_随机字符
                - 'date_only': YYYYMMDD_随机字符
            prefix (str): 文件夹名称前缀
            suffix (str): 文件夹名称后缀

        Returns:
            str: 生成的唯一文件夹名称
        """
        now = datetime.datetime.now()

        # 生成一个短的随机字符串（取UUID的前8位）
        random_str = str(uuid.uuid4())[:8]

        # 根据不同格式类型生成时间字符串
        if format_type == 'compact':
            time_str = now.strftime('%y%m%d%H%M%S')
        elif format_type == 'readable':
            time_str = now.strftime('%Y-%m-%d_%H-%M-%S')
        elif format_type == 'date_only':
            time_str = now.strftime('%Y%m%d')
        else:  # default
            time_str = now.strftime('%Y%m%d_%H%M%S')

        # 组合文件夹名称
        folder_name = f"{prefix}{'_' if prefix else ''}{time_str}_{random_str}{('_' + suffix) if suffix else ''}"

        return folder_name
    
    def generate_unique_string() -> str:
        """
        生成一个高度唯一的字符串（40个字符长）。

        该方法结合了当前精确到微秒的时间戳和随机的 UUID4，
        并通过 SHA1 哈希算法进行处理，以确保其唯一性、简洁性
        和固定长度。

        Returns:
            str: 唯一且长度固定的哈希字符串。
        """
        # 1. 获取当前精确到微秒的时间戳
        now = datetime.datetime.now()
        # 格式：YYYYMMDDhhmmssffffff (精确到微秒)
        timestamp_str = now.strftime("%Y%m%d%H%M%S%f")

        # 2. 生成一个随机的UUID (version 4)
        uuid_str = str(uuid.uuid4())

        # 3. 组合时间戳和UUID
        raw_unique_string = f"{timestamp_str}-{uuid_str}"

        # 4. 使用 SHA1 哈希算法进行处理，得到 40 个字符的十六进制字符串
        # 这一步是确保唯一性、固定长度和格式的关键
        hashed_string = hashlib.sha1(raw_unique_string.encode('utf-8')).hexdigest()

        return hashed_string
    
if __name__ == "__main__":
    file_name=FileNamer.generate_unique_string()
    print(file_name)