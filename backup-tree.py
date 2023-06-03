import os
import filecmp
import shutil
from typing import Dict, Tuple, Set, List
import locale
from pinyin import pinyin
from logger_config import logger
locale.setlocale(locale.LC_COLLATE, 'zh_CN.UTF-8')

default_ignore = {'$RECYCLE.BIN', 'RECYCLER', 'vod_cache_data'}

class BackupTree:

    def __init__(self, new_dir, old_dir, ignore_items):
        self.new_dir = new_dir
        self.old_dir = old_dir
        self.ignore_items = ignore_items
        self.del_files = set()
        self.add_files = set()
        self.modified_files = set()
        self.copy_no_file_dirs = set()
        self.del_no_file_dirs = set()

    def pre_check(self):

        if not os.path.exists(self.new_dir) or not os.path.exists(self.old_dir):
            if not os.path.exists(self.new_dir):
                logger.error(f"源路径不存在: {self.new_dir}")
            if not os.path.exists(self.old_dir):
                logger.error(f"目标路径不存在: {self.old_dir}")
            exit(1)

        expand_ignore = set()

        for item in self.ignore_items:

            new_dir_item = os.path.join(self.new_dir, item)
            old_dir_item = os.path.join(self.old_dir, item)

            flag = False  # item是否在两个目录均不存在

            if os.path.isfile(new_dir_item):
                expand_ignore.add(new_dir_item)
            elif os.path.isdir(new_dir_item):
                for cur_dir, _, files in os.walk(new_dir_item):
                    expand_ignore.add(cur_dir)
                    for file in files:
                        expand_ignore.add(os.path.join(cur_dir, file))
            else:
                flag = True

            if os.path.isfile(old_dir_item):
                expand_ignore.add(old_dir_item)
            elif os.path.isdir(old_dir_item):
                for cur_dir, _, files in os.walk(old_dir_item):
                    expand_ignore.add(cur_dir)
                    for file in files:
                        expand_ignore.add(os.path.join(cur_dir, file))
            else:
                if flag:
                    logger.warning(f"忽略项不存在: {item}")
                raise Exception(f"忽略项不存在: {item}")
                    
        self.ignore_items = expand_ignore

    def scan(self, mode: int) -> None:
        """mode: 0--忽略同名文件 1--比较同名文件"""
        def collect_files(root_dir: str) -> Set[str]:
            """返回去除忽略名单后的相对路径"""
            file_set = set()
            for cur_dir, _, files in os.walk(root_dir):
                if os.path.relpath(cur_dir, root_dir) in self.ignore_items:
                    continue
                for file in files:
                    rel_dir = os.path.relpath(os.path.join(cur_dir, file), root_dir)
                    if rel_dir in self.ignore_items:
                        continue
                    file_set.add(rel_dir)
            return file_set

        self.new_files = collect_files(self.new_dir)
        self.old_files = collect_files(self.old_dir)
        self.add_files = self.new_files - self.old_files
        self.del_files = self.old_files - self.new_files
        self.modified_files = set()

        if mode == 0:
            pass
        elif mode == 1:
            for file in self.new_files & self.old_files:
                if not filecmp.cmp(os.path.join(self.new_dir, file),
                                   os.path.join(self.old_dir, file)):
                    self.modified_files.add(file)
        else:
            raise Exception(f"Invalid mode({mode}) in function scan: \n\
                            0--不比较同名文件\n\
                            1--比较同名文件")

    def collect_no_file_dirs(self, root_dir: str) -> Set[str]:
        """返回所有空目录(相对路径)"""
        def layer_no_file_dir(dir: str) -> bool:
            for item in os.scandir(dir):
                if item.is_file():
                    return False
            return True

        suspect_set = set()
        dirty_set = set()

        for cur_dir, dirs, files in os.walk(root_dir):
            # 如果在忽略目录内，就下一次循环
            if cur_dir in self.ignore_items:
                continue

            if layer_no_file_dir(cur_dir):
                suspect_set.add(cur_dir)
            else:
                par_dir = cur_dir
                while True:
                    dirty_set.add(par_dir)
                    if os.path.samefile(par_dir, root_dir) or os.path.dirname(par_dir) in dirty_set:
                        break
                    par_dir = os.path.dirname(par_dir)

        rel_path_set = set()
        for dir in suspect_set - dirty_set:
            rel_path_set.add(os.path.relpath(dir, root_dir))

        return rel_path_set

    def reduce(self, dir_set: Set[str], root_dir: str) -> Set[str]:
        """返回在root_dir目录下, dir_set的合并集合"""
        # [父目录绝对路径, (0待定、1已满、-1未满), 子目录绝对路径集]
        self.dir_items: Dict[str, Tuple[int, Set[str]]] = {}

        def add_to_par(dir: str) -> None:
            """将参数加入字典键为父目录的值的集合中"""
            par_dir = os.path.dirname(dir)
            if not os.path.samefile(dir, root_dir):
                if par_dir not in self.dir_items:
                    self.dir_items[par_dir] = (0, set())
                self.dir_items[par_dir][1].add(dir)
            else:
                raise Exception(f"这里不应该出现根目录: {dir}")

        def single_reduce(dir: str) -> None:
            """发现一个新的满目录立即退出"""
            # 该目录下是否有文件或目录没包含
            for item in os.scandir(dir):
                # 若该项已有，直接下一个
                if item.path in self.dir_items[dir][1]:
                    continue
                # 若是文件没有，直接置-1返回
                if item.is_file():
                    self.dir_items[dir] = (-1, self.dir_items[dir][1])
                    return
                # 若是目录没有，直接退出
                if item.is_dir():
                    return

            # 到这步，说明该目录满
            self.dir_items[dir] = (1, self.dir_items[dir][1])
            self.add_dir = dir
            return

        # 全部记录字典
        for rel_item in dir_set:
            # 转换成绝对路径
            item = os.path.join(root_dir, rel_item)
            # 确保路径存在
            if not os.path.exists(item):
                raise Exception(f"该路径不存在: {item}")
            # 确保路径在根目录下
            if os.path.relpath(item, root_dir).startswith('..'):
                raise Exception(f"该路径不包含在根目录{root_dir}中: {item}")
            # 如果总目录已包含，直接返回即可
            if os.path.samefile(item, root_dir):
                return {item}
            # 不管是文件还是目录，将其记录在册
            add_to_par(item)
            # 若为目录，意为整个包含，额外将其子项全部标满
            if os.path.isdir(item):
                for cur_dir, dirs, files in os.walk(item):
                    if cur_dir in self.dir_items:
                        self.dir_items[cur_dir] = (1, self.dir_items[cur_dir][1])
                    else:
                        self.dir_items[cur_dir] = (1, set())
        # "合并同类项"
        while True:
            # 标记新检出的可以合并了的目录
            self.add_dir = ''
            for dir in self.dir_items:
                # 检查过的就不用管了
                if self.dir_items[dir][0] != 0:
                    continue
                single_reduce(dir)
                if self.add_dir:
                    break
            if self.add_dir:
                add_to_par(self.add_dir)
            else:
                break

        # 到这一步，标志为 0 或 -1 的都是未满
        reduced_set = set()
        for dir in self.dir_items:
            # 满的目录
            if self.dir_items[dir][0] == 1:
                # 父目录不在或者父目录未满，则获取其目录名
                if os.path.dirname(dir) not in self.dir_items or \
                        self.dir_items[os.path.dirname(dir)][0] != 1:
                    reduced_set.add(dir)
                # 父目录在而且也是满的，则没他啥事了
                else:
                    pass
            # 非满目录下有啥收啥
            else:
                for item in self.dir_items[dir][1]:
                    reduced_set.add(item)

        return reduced_set

    def sorted_reduce(self, file_set: Set[str], root_dir: str) -> List[str]:
        """reduce以后按文件夹、文件、拼音排序"""
        reduced_set = self.reduce(file_set, root_dir)
        return sorted(list(reduced_set), key=lambda item: (not os.path.isdir(item), pinyin(item) if item.isalpha() else locale.strxfrm(item)))

    def back_up_files(self, mode: int) -> None:
        """mode: 0--只增添文件 1--删除多余文件"""

        if mode == 1:
            logger.info("删除中......")
            for file in self.del_files:
                os.remove(os.path.join(self.old_dir, file))

        print(f"\033[32m复制新文件中......\033[0m")
        for file in self.add_files:
            dst_dirname = os.path.dirname(os.path.join(self.old_dir, file))
            # 正常情况下把目录建起来即可
            if not os.path.exists(dst_dirname):
                os.makedirs(dst_dirname)
            # 如果存在文件同名目录，却将错误地拷到这个目录下
            file_or_dir = os.path.join(self.old_dir, file)
            if os.path.isdir(file_or_dir):
                shutil.rmtree(file_or_dir)
            shutil.copy(os.path.join(self.new_dir, file), file_or_dir)

        for file in self.modified_files:
            shutil.copy(os.path.join(self.new_dir, file),
                        os.path.join(self.old_dir, file))

    def back_up_no_file_dirs(self) -> None:

        new_no_file_dirs = self.collect_no_file_dirs(self.new_dir)
        old_no_file_dirs = self.collect_no_file_dirs(self.old_dir)

        self.copy_no_file_dirs = new_no_file_dirs - old_no_file_dirs
        self.del_no_file_dirs = old_no_file_dirs - new_no_file_dirs

        for dir in self.copy_no_file_dirs:
            abs_dir = os.path.join(self.old_dir, dir)
            if not os.path.exists(abs_dir):
                os.makedirs(abs_dir)

        # copy_no_file_dirs要reduce需要另写一个reduce方法，先算了吧
        self.del_no_file_dirs = self.reduce(self.del_no_file_dirs, self.old_dir)

        for dir in self.del_no_file_dirs:
            if not os.path.exists(dir):
                raise Exception(f"这个目录应该存在: {dir}")
            else:
                shutil.rmtree(dir)

    
    def start(self):
        
        self.pre_check()
        self.scan(0)

        logger.info("发现这些目录是空的: ")
        for item in self.sorted_reduce(self.collect_no_file_dirs(self.new_dir), self.new_dir):
            logger.info(f"\t{item}")
        for item in self.sorted_reduce(self.collect_no_file_dirs(self.old_dir), self.old_dir):
            logger.info(f"\t{item}")
            
        logger.info("\n要增加的文件：")
        for item in self.sorted_reduce(self.add_files, self.new_dir):
            logger.info(f"\t{item}")

        logger.info("\n要覆盖的文件：")
        for item in self.sorted_reduce(self.modified_files, self.old_dir):
            logger.info(f"\t{item}")

        logger.info("\n要删除的文件：")
        for item in self.sorted_reduce(self.del_files, self.old_dir):
            logger.info(f"\t{item}")

        logger.info("是否执行备份? (输入y继续, 否则终止)......")
        proceed = input()
        logger.info(f"{proceed}")
        if proceed == 'y':
            self.back_up_files(1)
            self.back_up_no_file_dirs()
            logger.info("已新建的空文件夹:")
            for dir in self.copy_no_file_dirs:
                logger.info(f"\t{dir}")
            logger.info("已删除的空文件夹:")
            for dir in self.del_no_file_dirs:
                logger.info(f"\t{dir}")

            logger.info("备份结束")
        else:
            logger.info("扫描结束，未备份")

backup = BackupTree("F:", "E:\\backup\\longterm_storage", {})
# backup = BackupTree("old", "new", {})
backup.start()
