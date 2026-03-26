# llm_decision_making 与 robot_service 网络通信接口

## 1. 适用范围

这份文档只描述两个模块之间的通信：

- `llm_decision_making` 请求方
- `robot_service` 响应方

它只关注 **HTTP 协议层** 的约定，不关注两个模块内部如何实现。

## 2. 通信原则

`llm_decision_making` 与 `robot_service` 之间只通过 HTTP 传输数据。

## 3. 传输格式

当前实现约定：
- 协议：HTTP
- 编码：UTF-8
- 数据格式：JSON
- `Content-Type`：`application/json`

## 5. 当前已实现协议


## 7. llm_decision_making 当前可直接复用的接口





## 10. 推荐理解方式

如果只从协议层理解这两个模块，可以把它们看成：

- `llm_decision_making`
  - 负责发请求、收数据、做决策
- `robot_service`
  - 负责维护机器人侧状态并返回结果
