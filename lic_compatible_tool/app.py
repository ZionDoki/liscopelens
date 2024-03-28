# coding=utf-8
# Author: Zihao Zhang, Ziang Liu
# Date: 2023/12/18
# Contact: zhzihao2023@lzu.edu.cn, liuza20@lzu.edu.cn

import sys
import json
import argparse
from pprint import pformat

from .checker import infer
from .checker import compatible
from .utils import delete_duplicate_str

from loguru import logger

logger.remove()

def cli():
    parser = argparse.ArgumentParser(description="部件兼容性分析工具")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--sbom", help="部件sbom参数JSON字符串")
    group.add_argument("--sbom_file", help="部件sbom参数JSON文件清单路径")
    parser.add_argument("--output", type=str, default="", help="输出文件路径")
    parser.add_argument("--log-level", type=str, default="info", help="日志级别")
    parser.add_argument("--beauty", action="store_true", default=False, help="美化输出")
    parser.add_argument("--reinfer", action="store_true", default=False, help="强制更新知识库")
    args = parser.parse_args()

    logger.add(sys.stdout, colorize=True, level=args.log_level.upper())

    if args.sbom_file:
        with open(args.sbom_file, encoding="UTF-8") as f:
            input_params = f.read()
    else:
        input_params = args.sbom
    data = json.loads(input_params)

    conflicts = []
    get2 = compatible.Get(data)

    # * 1. 获取依赖关系和许可证，遍历json文件中的packages列表
    license_dict = get2.get_license()
    relationships = get2.get_reliance()

    logger.debug("所有组件的license引入情况：\n" + pformat(license_dict))
    logger.debug("所有组件的依赖情况：\n" + pformat(relationships))

    infer.generate_knowledge_graph()
    compatible_checker = compatible.CompatibleChecker()

    for x in relationships:
        get = compatible.Get(data)
        process = compatible.Process(license_dict)
        con = process.check(x, compatible_checker)
        license_dict = get.get_license()
        conflicts.extend(con)

    conflicts = delete_duplicate_str(conflicts)

    if args.output:
        with open(args.output, "w", encoding="UTF-8") as f:
            f.write(json.dumps(conflicts, indent=4 if args.beauty else None, ensure_ascii=False))
    else:
        print(json.dumps(conflicts, indent=4 if args.beauty else None, ensure_ascii=False))
