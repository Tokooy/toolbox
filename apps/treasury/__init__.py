# -*- coding: utf-8 -*-
"""美债收益率看板 · US Treasury Yield Dashboard

后端目录结构（自下而上，互不越层）：

* ``fred.py``    网络层：从 FRED 下载 DGS2 / DGS10 / DGS30 序列
* ``store.py``   存储层：本地缓存 CSV / meta.json 的读写与原子替换
* ``service.py`` 业务层：增量更新（refresh_data）与前端数据组装（load_data）
* ``api.py``     接口层：把业务能力暴露为 ``/api/treasury/*``
"""
