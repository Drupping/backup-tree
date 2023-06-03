# python bug?
# 116行父目录加入的时候会把无效的目录也加进来，貌似是defaultdict和dirname造成的
# 更诡异的是在123行尝试pop掉无效键值对的时候直接没法pop
# 可以构造用例，总目录e下包含文件夹：'e\\1', 'e\\1\\5', 文件：'e\\1\\3', 'e\\1\\4', 'e\\2'

import os
import filecmp
import shutil
from datetime import datetime
from collections import defaultdict
from typing import Dict, Tuple, Set


def classify(new_dir: str, old_dir: str) -> None:

    if not os.path.exists(new_dir) or not os.path.exists(old_dir):
        if not os.path.exists(new_dir):
            print(f"\033[31m源路径不存在：{new_dir}\033[0m")
        if not os.path.exists(old_dir):
            print(f"\033[31m目标路径不存在：{old_dir}\033[0m")
        return

    del_files = set()
    copy_files = set()
    cover_files = set()
    print_copy_emp_dirs = set()
    print_del_emp_dirs = set()

    def collect_files(root_dir: str) -> set:

        file_set = set()
        for root, dirs, files in os.walk(root_dir):
            for file in files:
                file_set.add(os.path.relpath(
                    os.path.join(root, file), root_dir))
        return file_set

    def collect_empty_dirs(root_dir: str) -> set:

        def is_empty_dir(dir: str) -> bool:
            for item in os.scandir(dir):
                if item.is_file():
                    return False
            return True

        suspect_set = set()
        dirty_set = set()

        for root, dirs, files in os.walk(root_dir):
            for dir in dirs:
                abs_dir = os.path.join(root, dir)
                if is_empty_dir(abs_dir):
                    suspect_set.add(os.path.relpath(abs_dir, root_dir))
                else:
                    while not os.path.samefile(abs_dir, root_dir):
                        dirty_set.add(os.path.relpath(abs_dir, root_dir))
                        abs_dir = os.path.dirname(abs_dir)
                        if os.path.relpath(abs_dir, root_dir) in dirty_set:
                            break

        return suspect_set - dirty_set

    def reduce(dir_set: set(), root_dir: str) -> set():

        if not dir_set:
            return set()

        dir_items: Dict[str, Tuple[int, Set[str]]] = defaultdict(
            lambda: (0, set()))  # 父目录， (0未遍历，1满，-1未满)， 子目录
        add_parent = set()

        def reduce_r(dir: str) -> bool:
            nonlocal dir_items
            nonlocal add_parent
            # 空目录判真, 或者上一轮已查过
            if dir_items[dir][0] != 0:
                return dir_items[dir][0]

            for item in os.scandir(dir):
                # 有子项没包含，判否
                if item.path not in dir_items[dir][1]:
                    dir_items[dir] = (-1, dir_items[dir][1])
                    return False
                # 如果是目录
                if item.is_dir():
                    # 该目录已满，跳过
                    if dir_items[item.path][0] == 1:
                        continue
                    # 该目录非满，直接判否
                    else:
                        if dir_items[item.path][0] == -1 or reduce_r(item.path) == -1:
                            dir_items[dir] = (-1, dir_items[dir][1])
                            return False

            dir_items[dir] = (1, dir_items[dir][1])
            # 一个非总目录已满且父目录不在，则记录它，出去加上它的父目录
            if os.path.dirname(dir) not in dir_set and not os.path.samefile(dir, root_dir):
                add_parent.add(dir)

            return True

        for item in dir_set:
            if not os.path.exists(item):
                raise Exception(f"该路径不存在: {item}")
            if os.path.relpath(item, root_dir).startswith('..'):
                raise Exception(f"该路径不包含在总目录{root_dir}中: {item}")
            if os.path.samefile(item, root_dir):
                return {root_dir}

            if os.path.isdir(item):
                dir_items[item] = (1, set())

        add_parent = dir_set
        while True:
            # 父目录加入
            for dir in add_parent:
                dir_items[os.path.dirname(dir)][1].add(dir)
            # 去除上一步因为dirname和defaultdict的原因引入的无聊多余项
            pop_set = set()
            for dir, tup in dir_items.items():
                if not tup[0] and not tup[1]:
                    pop_set.add(dir)
            for pop_item in pop_set:
                print(dir_items.pop(pop_item))
            # 开启新的一轮循环
            add_parent = set()
            for dir in dir_items.keys():
                reduce_r(dir)

            if not add_parent:
                break
        #
        reduced_set = set()
        for dir in dir_items:
            if dir_items[dir][0] == 1:
                if os.path.dirname(dir) not in dir_items or \
                        dir_items[os.path.dirname(dir)][0] == -1:  # 会不会有bug
                    reduced_set.add(dir)
                else:
                    pass
            else:
                for item in dir_items[dir][1]:
                    if os.path.isfile(item):
                        reduced_set.add(item)
        
        return reduced_set

    def scan() -> None:

        nonlocal del_files
        nonlocal copy_files
        nonlocal cover_files

        new_files = collect_files(new_dir)
        old_files = collect_files(old_dir)

        del_files = old_files - new_files
        copy_files = new_files - old_files
        common_files = new_files & old_files
        cover_files = set()
        # for file in common_files:
        #     if not filecmp.cmp(os.path.join(new_dir, file),
        #                        os.path.join(old_dir, file)):
        #         cover_files.add(file)

    def back_up_files() -> None:

        nonlocal del_files
        nonlocal copy_files
        nonlocal cover_files

        for file in del_files:
            os.remove(os.path.join(old_dir, file))

        for file in copy_files:
            dst_dirname = os.path.dirname(os.path.join(old_dir, file))
            if not os.path.exists(dst_dirname):
                os.makedirs(dst_dirname)
            file_or_dir = os.path.join(old_dir, file)
            if os.path.isdir(file_or_dir):
                if not next(os.scandir(file_or_dir), None):
                    raise Exception(f"这个目录不应该是非空的：{file_or_dir}")
                os.rmdir(file_or_dir)
            shutil.copy(os.path.join(new_dir, file), file_or_dir)

        for file in cover_files:
            shutil.copy(os.path.join(new_dir, file),
                        os.path.join(old_dir, file))

    def back_up_emp_dirs() -> None:

        nonlocal print_copy_emp_dirs
        nonlocal print_del_emp_dirs
        new_emp_dirs = collect_empty_dirs(new_dir)
        old_emp_dirs = collect_empty_dirs(old_dir)

        copy_emp_dirs = new_emp_dirs - old_emp_dirs
        del_emp_dirs = old_emp_dirs - new_emp_dirs

        for dir in copy_emp_dirs:
            abs_dir = os.path.join(old_dir, dir)
            if os.path.exists(abs_dir):
                del_emp_dirs -= collect_empty_dirs(abs_dir)
                shutil.rmtree(abs_dir)
            else:
                print_copy_emp_dirs.add(dir)
            os.makedirs(abs_dir)

        while (del_emp_dirs):
            next_set = set()
            for dir in del_emp_dirs:
                if os.path.exists(os.path.join(new_dir, dir)):
                    continue
                abs_dir = os.path.join(old_dir, dir)
                os.rmdir(abs_dir)
                if not next(os.scandir(os.path.dirname(abs_dir)), None):
                    next_set.add(os.path.dirname(dir))
                print_del_emp_dirs.add(dir)
            del_emp_dirs = next_set

    dir_set = set()
    root_dir = 'e'
    for root, dirs, files in os.walk(root_dir):
        for dir in dirs:
            dir_set.add(os.path.join(root, dir))
        # for file in files:
        #     dir_set.add(os.path.join(root, file))
    dir_set = {'e\\1\\5', 'e\\1\\3', 'e\\1\\4', 'e\\2'}
    print(dir_set)
    print(reduce(dir_set, root_dir))
    # timestr = datetime.now().strftime("%Y%m%d%H%M%S")
    # with open('backup_' + timestr + '.log', 'w', encoding="utf-8") as f:

    #     scan()

    #     print("要增加的文件：")
    #     f.write("要增加的文件：\n")
    #     for file in sorted(list(copy_files)):
    #         print(f"\t\033[32m{file}\033[0m")
    #         f.write(f"\t{file}\n")

    #     print("要覆盖的文件：")
    #     f.write("要覆盖的文件：\n")
    #     for file in sorted(list(cover_files)):
    #         print(f"\t\033[33m{file}\033[0m")
    #         f.write(f"\t{file}\n")

    #     print("要删除的文件：")
    #     f.write("要删除的文件：\n")
    #     for file in sorted(list(del_files)):
    #         print(f"\t\033[31m{file}\033[0m")
    #         f.write(f"\t{file}\n")

    #     # proceed = input("\033[3m是否执行备份? (输入y继续，否则终止)......\n\033[0m")
    #     # f.write("是否执行备份? (输入y继续，否则终止)......\n" + proceed)
    #     proceed = 'y'
    #     if proceed == 'y':
    #         back_up_files()
    #         back_up_emp_dirs()
    #         print("已删除的空文件夹：")
    #         f.write("已删除的空文件夹：\n")
    #         for dir in print_del_emp_dirs:
    #             print(f"\t\033[31m{dir}\033[0m")
    #             f.write(f"\t{dir}\n")
    #         print("已新建的空文件夹：")
    #         f.write("已新建的空文件夹：\n")
    #         for dir in print_copy_emp_dirs:
    #             print(f"\t\033[32m{dir}\033[0m")
    #             f.write(f"\t{dir}\n")

    #         print("\033[32m备份结束\033[0m")
    #         f.write("备份结束\n")
    #     else:
    #         print("\033[33m扫描结束，未备份\033[0m")
    #         f.write("扫描结束，未备份\n")


# classify("E:\\longterm_storage", "F:\\")
# classify("2", "new")
# classify("3", "old")
# classify("new", "old")
classify("new", "old")
