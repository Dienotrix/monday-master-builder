# Notes kept for comparison only

The build order starts with the workspace, then the folders, then every board in the order the blueprint lists them, and only then the automations. A read after every write proves the object exists before the next one depends on it.

Labels: intro, discovery, reverse-demo, prototype-review, demo, sign-off, expansion, pricing, call-review, scoping, working-session, support, check-in

| key | kind | owner |
|---|---|---|
| B1 | board | account-build |
| B1.C3 | column | account-build |

```text
create_board, create_column, create_group, create_item, change_item_column_values
```

Seat values: partner-led | co-sell | vendor-led | client-led
