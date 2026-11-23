# 澄河观测日账镜像

澄河流域资料中心用两个独立 SQLite 库完成源站供数与异地核账。采集台交来按原顺序排列的站日观测。汇交员固定运输件，异地值班员可在源库关闭后继续收件和落账，稽核员按原号核对每次正式办理。

## 按班办理

1. 源站录入原批，固定事实键、行序和首次正式出处。
2. 汇交员按指定正式批发行底件，即使之后已有正式更正，也能取到旧截面。
3. 值班员实收底件并安装，核对站日原序明细和总量。
4. 源站核对成组前像后正式提交更正。读数相同的新测读也产生独立修订和出处。
5. 汇交员按正式更正批号领取固定增量件与发行首执。
6. 异地值班员按实际到件顺序实收与落账。缺少相关前序时，保持原实收号等待续办。
7. 夜班从正式镜像领取同一快照的明细、出处、行数和整数升数。
8. 稽核员按交付号复领历史首执。补到所需前序并正式入账后，沿原实收号续办待件。

## 运行

需要 Python 3.11 和标准库，无需安装依赖。在项目根目录运行。

```sh
python3 -B check_project.py
python3 -B -m demo
```

独立查看 unittest 时，可运行 `python3 -B -m unittest discover -s tests -t .`。演示使用 `samples/open_day.json` 和 `samples/corrections.json`，在独立临时目录建立库。开账样例的 7 L、实测 0 L、缺测共三行，合计 7 L。增量样例先收到 T2、T3，此时 A 保留初测的 7 L，B 已为 8 L，T3 待办且无首执。补到并落账 T1 后，T3 续办成功，日账为 13 L、9 L，合计 22 L。T1 的历史首执仍保留等值复测的来源。

## Python 接口

调用方打开普通 `sqlite3.Connection`。源库调用 `source.revisions.initialize_source_schema(db)` 与 `publication.register.initialize_publication_schema(db)`。异地库调用 `mirror.facts.initialize_mirror_schema(db, mirror, stream)` 与 `receiving.store.initialize_inbox_schema(db)`。同一异地库可配置多个各自绑定源流的镜像标识。初始化可重复执行，保留已办理记录。同一镜像标识绑定另一源流时拒绝。公开办理函数管理自身事务，调用时连接须处于事务之外。

| 办理 | 调用 | 成功结果 |
| --- | --- | --- |
| 源站开账 | `source.intake.record(db, stream, batch, rows)` | 含 `batch`, `sequence`, `stream`, `receipt_id`, `kind` 的源回执 |
| 源站更正 | `source.corrections.amend(db, stream, batch, changes)` | 正式更正的源回执 |
| 底件发行 | `publication.bootstrap.bootstrap(db, stream, start_batch)` | 含 `envelope` 字节串和 `receipt` 的发行结果 |
| 增量发行 | `publication.changes.issue(db, batch)` | 原固定件和原发行首执 |
| 异地实收 | `receiving.inbox.receive(db, mirror, envelope)` | 含 `intake_id`, `delivery_id`, `pending` 的实收记录 |
| 安装或落账 | `mirror.posting.post(db, mirror, intake_id)` | `status` 为 `posted` 时附原 `receipt`，为 `pending` 时首执为空并给出 `waiting_for` |
| 待办查询 | `receiving.pending.list_pending(db, mirror)` | 依实收号排列的持久待办，可用原号续办 |
| 站日查询 | `audit.daybook.read_day(db, mirror, station, day)` | `start`, `rows`, `row_count`, `total_litres`，并回显站日 |
| 历史首执 | `audit.history.receipt(db, mirror, delivery_id)` | 原成功首执及其 `sources` |

行形如 `{"key": ["南闸", "2025-05-16", "A"], "reading": {"litres": 7, "missing": false, "origin": "晨班尺"}}`。站名、观测编号和出处为非空文本，日期为 `YYYY-MM-DD`。实测为非负整数升，布尔值不能当升数。缺测用 `{"litres": null, "missing": true, "origin": "未到表"}`，参与行数及明细。总量使用 Python 整数求和，升数以 JSON 整数字面量保存在 SQLite 文本中。固定行序跨修订保持，计算无需舍入。已安装但无事实的站日返回空明细和两个零。

 `source.revisions.get_current_facts(db, stream)` 返回按源行序排列的事实记录。每项更正形如 `{"key": key, "before": current_fact, "after": new_reading}`，其中 `before` 是该键的完整事实记录，`after` 使用 `reading` 的格式。一个源库内的原批号与办理号共用唯一编号空间，正式序号按源流递增。重复批号或事实键、非法观测及无效前像均抛出 `ValueError`，整批保持原状。`source.receipts.get_source_receipt` 按批号查询原源执。未正式提交或类型错误的发行请求抛出 `ValueError`。

底件覆盖指定截面已有的事实。增量只更正既有事实。旧底件没有某键的原始行时，可用包含该行的新底件配置另一镜像。已安装镜像的起点保持固定。被起点覆盖的更正无需重复办理。件外层版本为 1，传输字节包括种类、源流、交付号、冻结正文和完整性摘要。交给 `receive` 的是发行结果的 `envelope`。实收仅登记物料，正式成功首执由 `post` 产生。坏件、错流、同号异件、未安装时落增量及不相容起点均抛出 `ValueError`。未知本地实收号或无成功首执的交付号抛出 `LookupError`。正式写入的 SQLite 异常原样返回，已暂写的整组结果随事务回滚，实收物料可以重试。
