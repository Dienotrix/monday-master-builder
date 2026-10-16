# Audit of 001/v0.2

Internal: never client-facing. A planted audit file for the compare fixture: its documents appendix
holds the read-only documents the audit says it ran, and the scan reads every one of them.

## Window

Before snapshot 2026-10-16T09:00:00Z, after snapshot 2026-10-16T11:00:00Z.

## Documents appendix

Document 1, a mutation:

```graphql
mutation {
  archive_board(board_id: "90300000301") { id }
}
```

Document 2, a subscription:

```graphql
subscription {
  board_updated(board_id: "90300000301") { id }
}
```

Document 3, two operations in one document:

```gql
query First { boards(ids: ["90300000301"]) { id name } }
query Second { boards(ids: ["90300000302"]) { id state } }
```

Document 4, a clean query:

```graphql
query {
  boards(ids: ["90300000301"], state: all) { id name state description }
}
```

Document 5, the word mutation inside a string:

```graphql
query ($term: String = "mutation") {
  boards(ids: ["90300000301"]) {
    items_page(limit: 5, query_params: {rules: [{column_id: "name", compare_value: ["mutation { x }"]}]}) {
      items { id }
    }
  }
}
```

Document 6, the word mutation inside a comment:

```graphql
# mutation { delete_board(board_id: "90300000301") { id } } was considered and not run
query {
  me { id }
}
```

Document 7, a query string inside a JSON block:

```json
{"query": "query { boards(ids: [\"90300000305\"]) { id updated_at } }", "variables": {}}
```

## Notes

Outside the appendix: this block is not a document and the scan never reads it.

```graphql
mutation { delete_board(board_id: "90300000309") { id } }
```
