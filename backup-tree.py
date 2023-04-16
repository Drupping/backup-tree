# 文件夹问题

import os
import filecmp
import shutil
new_version_root = r"F:\ZJU"
old_version_root = r"E:\longterm_storage\ZJU"


def set_dir(root_dir: str) -> list:
    """返回入参根目录的所有文件相对路径的list"""
    file_list = []

    for root, dirs, files in os.walk(root_dir):
        for file in files:
            file_list.append(os.path.relpath(
                os.path.join(root, file), root_dir))

    return file_list

def copy_ensure(src_file: str, dst_file: str):
    """保证复制过去的文件，所在目录存在"""
    dst_dirname = os.path.dirname(dst_file)
    if not os.path.exists(dst_dirname):
        os.makedirs(dst_dirname)
    shutil.copy(src_file, dst_file)

def do_backup(to_copy: list, to_del: list, to_cover: set) -> None:
    """对3类改动执行备份操作"""
    for file_to_copy in to_copy:
        copy_ensure(os.path.join(new_version_root, file_to_copy),
                    os.path.join(old_version_root, file_to_copy))

    for file_to_del in to_del:
        os.remove(os.path.join(old_version_root, file_to_del))

    for file_to_cover in to_cover:
        copy_ensure(os.path.join(new_version_root, file_to_cover),
                    os.path.join(old_version_root, file_to_cover))

def load_diff(to_copy: list, to_del: list, to_cover: set) -> None:

    list_new = set_dir(new_version_root)
    list_old = set_dir(old_version_root)

    to_copy = list(set(list_new) - set(list_old))
    to_del = list(set(list_old) - set(list_new))

    set_common = set(list_new) & set(list_old)
    to_cover = set()
    for common in set_common:
        if not filecmp.cmp(os.path.join(new_version_root, common),
                           os.path.join(old_version_root, common)):
            to_cover.add(common)

to_copy = []
to_del = []
to_cover = ()

list_new = set_dir(new_version_root)
list_old = set_dir(old_version_root)

to_copy = list(set(list_new) - set(list_old))
to_del = list(set(list_old) - set(list_new))

set_common = set(list_new) & set(list_old)
to_cover = set()
for common in set_common:
    if not filecmp.cmp(os.path.join(new_version_root, common),
                        os.path.join(old_version_root, common)):
        to_cover.add(common)

print("要增加的文件：")
for file in to_copy:
    print(f"\t{file}")

print("要覆盖的文件：")
for file in to_cover:
    print(f"\t{file}")

print("要删除的文件：")
for file in to_del:
    print(f"\t{file}")

# do_backup(to_copy, to_del, to_cover)