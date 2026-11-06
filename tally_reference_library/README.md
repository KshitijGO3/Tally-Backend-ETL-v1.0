# Tally Reference Library

This reference library contains the official documentation, sample payloads, API specifications, and extracted templates downloaded directly from:
- **TallyHelp Integration Guide:** https://help.tallysolutions.com/tally-prime-integration-using-json-1/
- **TallyPrime API Explorer Sandbox:** https://tallysolutions.com/tallyprime-api-explorer/
- **TallyConnector Postman XML Collection:** https://documenter.getpostman.com/view/13855108/TzeRpAMt

---

## 1. Directory Structure & Downloaded Files

| File | Type | Description |
|---|---|---|
| `postman_tally_xmls_reference.md` | Markdown | Complete archive of the TallyConnector Postman XML repository (`TzeRpAMt`) with all 41 requests, TDL reports, and MAV-safe XML rules |
| `api_explorer_payloads.md` | Markdown | All 69 JSON request templates extracted from the TallyPrime API Explorer sandbox |
| `tally_prime_integration_using_json.html` | HTML | Complete offline HTML mirror of the official TallyPrime JSON integration guide |
| `api_explorer.html` | HTML | Offline mirror of the TallyPrime API Explorer sandbox |
| `api_explorer_assets/` | Folder | Full JavaScript engine (`script.js` containing all API templates), CSS, and libraries |
| `Ledger-Collection-Payload.txt` / `.docx` | Sample | Official Ledger collection request payload with `fetch_list` |
| `Ledger-Collection-Response.txt` / `.docx` | Sample | Official response payload for Ledger collection export |
| `Ledger-Creation-Payload.txt` / `.docx` | Sample | Official payload for creating a Ledger in Tally via JSON |
| `Ledger-Creation-Response.txt` / `.docx` | Sample | Official response after creating a Ledger |
| `Stock-Item-Collection-Payload.txt` / `.docx` | Sample | Official Stock Item collection request |
| `Stock-Item-Collection-Response.txt` / `.docx` | Sample | Official Stock Item collection response |
| `Stock-Item-Creation-Payload.txt` / `.docx` | Sample | Official Stock Item creation payload |
| `voucher-collection-payload.txt` / `.docx` | Sample | Official Voucher collection payload using `tdlmessage` and `Native Method` |
| `voucher-collection-response.txt` / `.docx` | Sample | Official Voucher collection response |
| `Voucher-Import-Payload.txt` / `.docx` | Sample | Official Voucher creation/import payload |
| `Voucher-Import-Response.txt` / `.docx` | Sample | Official Voucher import response |
| `Payloadutf8.txt` / `PayloadUTF16.txt` | Sample | Standard static variables payload for JSON export (`svExportFormat`, `svCurrentCompany`) |
| `objectRequestutf8.txt` / `objectrequestutf16.txt` | Sample | Object request payload using `fetch_list` |
| `ObjectResponse.txt` / `.docx` | Sample | Response for Object export request |
| `CollectionResponse.txt` / `.docx` | Sample | Response for Collection export request |
| `Balance-Sheet-Payload-*.txt` / `.docx` | Sample | Default and empty-field Balance Sheet report requests and responses |
| `PlainJSONSVPayload.txt` / `.docx` | Sample | Request using system variable `SVExportInPlainFormat: Yes` |
| `PlainJSONSVResponse.txt` / `.docx` | Sample | Plain JSON unadorned response structure |
| `PlainJSONTDLPayload.txt` / `.docx` | Sample | TDL report modification request for plain format |

---

## 2. Key Insights from Official Tally Sources

### 2.1 The Two Fundamental Export Paradigms

TallyPrime supports two primary export request modes via its HTTP JSON interface:

#### Paradigm A: Object Export (Single Entity Detail with `fetch_list`)
Used for retrieving the full attributes of a specific named entity (such as `Company`, `Ledger`, `StockItem`).
- **HTTP Headers:**
  ```http
  content-type: application/json
  version: 1
  tallyrequest: export
  type: object
  subtype: <EntityType>   # e.g., Company, Ledger, Group, StockItem
  id: <EntityName>        # e.g., "Bhrama Enterprises", "Kotak Bank"
  ```
- **JSON Request Body:**
  ```json
  {
    "static_variables": [
      { "name": "svExportFormat", "value": "jsonEx" },
      { "name": "svCurrentCompany", "value": "Bhrama Enterprises" }
    ],
    "fetch_list": [
      "Name",
      "Guid",
      "StartingFrom",
      "BooksFrom",
      "GSTIN",
      "MasterId"
    ]
  }
  ```
- **Response:** Returns `tallymessage: [...]` containing the exact requested fields including `guid`, `startingfrom`, `booksfrom`, and `masterid`.

#### Paradigm B: Collection Export (Bulk Query with `tdlmessage`)
Used for extracting all records of a given type with custom attributes.
- **HTTP Headers:**
  ```http
  content-type: application/json
  version: 1
  tallyrequest: export
  type: collection
  id: <CustomCollectionName>   # e.g., "TSPLGroups", "TSPLStockItems"
  ```
- **JSON Request Body:**
  ```json
  {
    "static_variables": [
      { "name": "svExportFormat", "value": "jsonex" },
      { "name": "svCurrentCompany", "value": "Bhrama Enterprises" }
    ],
    "tdlmessage": [
      {
        "definitions": [
          {
            "metadata": {
              "name": "<CustomCollectionName>",
              "type": "Collection"
            },
            "attributes": [
              { "Type": "<BaseType>" },
              { "Native Method": "Field1, Field2, Field3, ..." }
            ]
          }
        ]
      }
    ]
  }
  ```
- **Response:** Returns `data.collection: [...]` where every item contains the fields defined in `Native Method`.

#### Paradigm C: Day Book Report Export (Vouchers)
Used for extracting all transaction vouchers safely with date ranges without triggering C++ engine crashes.
- **HTTP Headers:**
  ```http
  content-type: application/json
  version: 1
  tallyrequest: export
  type: data
  id: Day Book
  ```
- **JSON Request Body:**
  ```json
  {
    "static_variables": [
      { "name": "svExportFormat", "value": "jsonex" },
      { "name": "svCurrentCompany", "value": "Bhrama Enterprises" },
      { "name": "svFromDate", "value": "20250401" },
      { "name": "svToDate", "value": "20260331" }
    ]
  }
  ```
- **Response:** Returns `data.tallymessage: [...]` containing all vouchers with line item allocations (`ledgerentries` and `allinventoryentries`).
