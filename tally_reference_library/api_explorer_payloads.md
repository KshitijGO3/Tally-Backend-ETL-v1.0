# TallyPrime API Explorer — Extracted JSON Request Templates

## Template 1

```json
{
  "static_variables": [
    {
      "name": "svMstImportFormat",
      "value": "jsonex"
    },
    {
      "name": "svCurrentCompany",
      "value": "Bhrama Enterprises"
    }
  ],
  "tallymessage": [
    {
      "metadata": {
        "type": "Ledger",
        "action": "create",
        "name": "Bank Of Baroda"
      },
      "name": "Bank Of Baroda",
      "parent": "Bank Accounts"
    }
  ]
}
```

## Template 2

```json
{
  "static_variables": [
    {
      "name": "svMstImportFormat",
      "value": "jsonex"
    },
    {
      "name": "svCurrentCompany",
      "value": "Bhrama Enterprises"
    }
  ],
  "tallymessage": [
    {
      "metadata": {
        "type": "Ledger",
        "action": "Alter",
        "name": "Bank Of Baroda"
      },
      "Opening Balance": "3000"
    }
  ]
}
```

## Template 3

```json
{
  "static_variables": [
    {
      "name": "svMstImportFormat",
      "value": "jsonex"
    },
    {
      "name": "svCurrentCompany",
      "value": "Bhrama Enterprises"
    }
  ],
  "tallymessage": [
    {
      "metadata": {
        "type": "Ledger",
        "action": "Delete",
        "name": "Bank Of Baroda"
      }
    }
  ]
}
```

## Template 4

```json
{
  "static_variables": [
    {
      "name": "svExportFormat",
      "value": "jsonEx"
    },
    {
      "name": "svCurrentCompany",
      "value": "Bhrama Enterprises"
    }
  ],
  "fetch_list": [
    "Name",
    "Parent",
    "Opening Balance",
    "Closing Balance"
  ]
}
```

## Template 5

```json
{
  "static_variables": [
    {
      "name": "svExportFormat",
      "value": "jsonex"
    },
    {
      "name": "svCurrentCompany",
      "value": "Bhrama Enterprises"
    }
  ]
}
```

## Template 6

```json
{
  "static_variables": [
    {
      "name": "svExportFormat",
      "value": "jsonex"
    },
    {
      "name": "svCurrentCompany",
      "value": "Bhrama Enterprises"
    }
  ],
  "tdlmessage": [
    {
      "definitions": [
        {
          "metadata": {
            "name": "TSPLBankLedgers",
            "type": "Collection"
          },
          "attributes": [
            {
              "Type": "Ledger"
            },
            {
              "Child Of": "$$GroupBank"
            },
            {
              "Native Method": "Name, Parent, OpeningBalance, ClosingBalance, IseBankingEnabled, Mailing Name, Bank Details"
            }
          ]
        }
      ]
    }
  ]
}
```

## Template 7

```json
{
  "static_variables": [
    {
      "name": "svMstImportFormat",
      "value": "jsonex"
    },
    {
      "name": "svCurrentCompany",
      "value": "Bhrama Enterprises"
    }
  ],
  "tallymessage": [
    {
      "metadata": {
        "type": "Group",
        "action": "create",
        "name": "North Bank Accounts"
      },
      "name": "North Bank Accounts",
      "parent": "Bank Accounts"
    }
  ]
}
```

## Template 8

```json
{
  "static_variables": [
    {
      "name": "svMstImportFormat",
      "value": "jsonex"
    },
    {
      "name": "svCurrentCompany",
      "value": "Bhrama Enterprises"
    }
  ],
  "tallymessage": [
    {
      "metadata": {
        "type": "Group",
        "action": "Alter",
        "name": "North Bank Accounts"
      },
      "name": "North Bank Accounts",
      "IsSubLedger": "yes"
    }
  ]
}
```

## Template 9

```json
{
  "static_variables": [
    {
      "name": "svMstImportFormat",
      "value": "jsonex"
    },
    {
      "name": "svCurrentCompany",
      "value": "Bhrama Enterprises"
    }
  ],
  "tallymessage": [
    {
      "metadata": {
        "type": "Group",
        "action": "Delete",
        "name": "North Bank Accounts"
      }
    }
  ]
}
```

## Template 10

```json
{
  "static_variables": [
    {
      "name": "svExportFormat",
      "value": "jsonEx"
    },
    {
      "name": "svCurrentCompany",
      "value": "Bhrama Enterprises"
    }
  ],
  "fetch_list": [
    "Name",
    "Parent",
    "Parent Hierarchy",
    "Opening Balance",
    "Closing Balance"
  ]
}
```

## Template 11

```json
{
  "static_variables": [
    {
      "name": "svExportFormat",
      "value": "jsonex"
    },
    {
      "name": "svCurrentCompany",
      "value": "Bhrama Enterprises"
    }
  ]
}
```

## Template 12

```json
{
  "static_variables": [
    {
      "name": "svExportFormat",
      "value": "jsonex"
    },
    {
      "name": "svCurrentCompany",
      "value": "Bhrama Enterprises"
    }
  ],
  "tdlmessage": [
    {
      "definitions": [
        {
          "metadata": {
            "name": "TSPLAssetGroups",
            "type": "Collection"
          },
          "attributes": [
            {
              "Type": "Group"
            },
            {
              "Child Of": "$$GroupCurrentAssets"
            },
            {
              "Belongs To": "Yes"
            },
            {
              "Native Method": "Name, Parent, IsSubledger, IsRevenue, Parent Hierarchy"
            }
          ]
        }
      ]
    }
  ]
}
```

## Template 13

```json
{
  "static_variables": [
    {
      "name": "svMstImportFormat",
      "value": "jsonex"
    },
    {
      "name": "svCurrentCompany",
      "value": "Bhrama Enterprises"
    }
  ],
  "tallymessage": [
    {
      "metadata": {
        "type": "Stock Item",
        "name": "Tea Powder",
        "action": "create"
      },
      "name": "Tea Powder",
      "parent": "\\u0004 Primary",
      "base units": "nos"
    }
  ]
}
```

## Template 14

```json
{
  "static_variables": [
    {
      "name": "svMstImportFormat",
      "value": "jsonex"
    },
    {
      "name": "svCurrentCompany",
      "value": "Bhrama Enterprises"
    }
  ],
  "tallymessage": [
    {
      "metadata": {
        "type": "Stock Item",
        "name": "Tea Powder",
        "action": "Alter"
      },
      "opening balance": " 200 nos"
    }
  ]
}
```

## Template 15

```json
{
  "static_variables": [
    {
      "name": "svMstImportFormat",
      "value": "jsonex"
    },
    {
      "name": "svCurrentCompany",
      "value": "Bhrama Enterprises"
    }
  ],
  "tallymessage": [
    {
      "metadata": {
        "type": "Stock Item",
        "name": "Tea Powder",
        "action": "Delete"
      }
    }
  ]
}
```

## Template 16

```json
{
  "static_variables": [
    {
      "name": "svExportFormat",
      "value": "jsonEx"
    },
    {
      "name": "svCurrentCompany",
      "value": "Bhrama Enterprises"
    }
  ],
  "fetch_list": [
    "Name",
    "Parent",
    "Opening Balance",
    "Closing Balance"
  ]
}
```

## Template 17

```json
{
  "static_variables": [
    {
      "name": "svExportFormat",
      "value": "jsonex"
    },
    {
      "name": "svCurrentCompany",
      "value": "Bhrama Enterprises"
    }
  ]
}
```

## Template 18

```json
{
  "static_variables": [
    {
      "name": "svExportFormat",
      "value": "jsonex"
    },
    {
      "name": "svCurrentCompany",
      "value": "Bhrama Enterprises"
    }
  ],
  "tdlmessage": [
    {
      "definitions": [
        {
          "metadata": {
            "name": "TSPLStockOfGroup",
            "type": "Collection"
          },
          "attributes": [
            {
              "Type": "StockItem"
            },
            {
              "Child Of": "\\"Gadgets\\""
            },
            {
              "Native Method": "Name, Parent, ClosingBalance, ClosingValue, BaseUnits"
            }
          ]
        }
      ]
    }
  ]
}
```

## Template 19

```json
{
  "static_variables": [
    {
      "name": "svMstImportFormat",
      "value": "jsonex"
    },
    {
      "name": "svCurrentCompany",
      "value": "Bhrama Enterprises"
    }
  ],
  "tallymessage": [
    {
      "metadata": {
        "type": "Stock Group",
        "action": "create",
        "name": "Tea Products"
      },
      "name": "Tea Products"
    }
  ]
}
```

## Template 20

```json
{
  "static_variables": [
    {
      "name": "svMstImportFormat",
      "value": "jsonex"
    },
    {
      "name": "svCurrentCompany",
      "value": "Bhrama Enterprises"
    }
  ],
  "tallymessage": [
    {
      "metadata": {
        "type": "Stock Group",
        "action": "Alter",
        "name": "Tea Products"
      },
      "name": "Tea Products",
      "isaddable": "Yes"
    }
  ]
}
```

## Template 21

```json
{
  "static_variables": [
    {
      "name": "svMstImportFormat",
      "value": "jsonex"
    },
    {
      "name": "svCurrentCompany",
      "value": "Bhrama Enterprises"
    }
  ],
  "tallymessage": [
    {
      "metadata": {
        "type": "Stock Group",
        "action": "Delete",
        "name": "Tea Products"
      }
    }
  ]
}
```

## Template 22

```json
{
  "static_variables": [
    {
      "name": "svExportFormat",
      "value": "jsonEx"
    },
    {
      "name": "svCurrentCompany",
      "value": "Bhrama Enterprises"
    }
  ],
  "fetch_list": [
    "Name",
    "Parent",
    "Opening Balance",
    "Closing Balance"
  ]
}
```

## Template 23

```json
{
  "static_variables": [
    {
      "name": "svExportFormat",
      "value": "jsonex"
    },
    {
      "name": "svCurrentCompany",
      "value": "Bhrama Enterprises"
    }
  ]
}
```

## Template 24

```json
{
  "static_variables": [
    {
      "name": "svExportFormat",
      "value": "jsonex"
    },
    {
      "name": "svCurrentCompany",
      "value": "Bhrama Enterprises"
    }
  ],
  "tdlmessage": [
    {
      "definitions": [
        {
          "metadata": {
            "name": "TSPL Stock Group ZeroBal",
            "type": "Collection"
          },
          "attributes": [
            {
              "Type": "StockGroup"
            },
            {
              "Native Method": "Name, Parent, Openingbalance, ClosingBalance"
            },
            {
              "Filters": "TSPL Zero Closing"
            }
          ]
        },
        {
          "metadata": {
            "name": "TSPL ZeroClosing",
            "type": "System",
            "sys_type": "Formulae"
          },
          "value": "$ClosingBalance = 0"
        }
      ]
    }
  ]
}
```

## Template 25

```json
{
  "static_variables": [
    {
      "name": "svMstImportFormat",
      "value": "jsonex"
    },
    {
      "name": "svCurrentCompany",
      "value": "Bhrama Enterprises"
    }
  ],
  "tallymessage": [
    {
      "metadata": {
        "type": "Unit",
        "action": "create",
        "name": "box"
      },
      "name": "box",
      "originalname": "boxes",
      "issimpleunit": true
    }
  ]
}
```

## Template 26

```json
{
  "static_variables": [
    {
      "name": "svMstImportFormat",
      "value": "jsonex"
    },
    {
      "name": "svCurrentCompany",
      "value": "Bhrama Enterprises"
    }
  ],
  "tallymessage": [
    {
      "metadata": {
        "type": "Unit",
        "action": "create",
        "name": "KG of 1000 gm"
      },
      "name": "KG of 1000 gm",
      "baseunits": "Kg",
      "additionalunits": "gm",
      "issimpleunit": false,
      "conversion": " 1000"
    }
  ]
}
```

## Template 27

```json
{
  "static_variables": [
    {
      "name": "svMstImportFormat",
      "value": "jsonex"
    },
    {
      "name": "svCurrentCompany",
      "value": "Bhrama Enterprises"
    }
  ],
  "tallymessage": [
    {
      "metadata": {
        "type": "Unit",
        "action": "Alter",
        "name": "box"
      },
      "name": "box",
      "decimalplaces": " 2"
    }
  ]
}
```

## Template 28

```json
{
  "static_variables": [
    {
      "name": "svMstImportFormat",
      "value": "jsonex"
    },
    {
      "name": "svCurrentCompany",
      "value": "Bhrama Enterprises"
    }
  ],
  "tallymessage": [
    {
      "metadata": {
        "type": "Unit",
        "action": "Delete",
        "name": "box"
      }
    }
  ]
}
```

## Template 29

```json
{
  "static_variables": [
    {
      "name": "svExportFormat",
      "value": "jsonEx"
    },
    {
      "name": "svCurrentCompany",
      "value": "Bhrama Enterprises"
    }
  ],
  "fetch_list": [
    "Name"
  ]
}
```

## Template 30

```json
{
  "static_variables": [
    {
      "name": "svExportFormat",
      "value": "jsonex"
    },
    {
      "name": "svCurrentCompany",
      "value": "Bhrama Enterprises"
    }
  ]
}
```

## Template 31

```json
{
  "static_variables": [
    {
      "name": "svVchImportFormat",
      "value": "jsonex"
    },
    {
      "name": "svCurrentCompany",
      "value": "Bhrama Enterprises"
    }
  ],
  "tallymessage": [
    {
      "metadata": {
        "type": "Voucher",
        "vchtype": "Payment",
        "action": "Create",
        "objview": "Accounting Voucher View"
      },
      "date": "20250831",
      "vouchertypename": "Payment",
      "partyledgername": "Akshaya Enterprises",
      "persistedview": "Accounting Voucher View",
      "allledgerentries": [
        {
          "ledgername": "Akshaya Enterprises",
          "isdeemedpositive": true,
          "ispartyledger": true,
          "amount": "-200.00",
          "billallocations": [
            {
              "name": "16",
              "billtype": "New Ref",
              "amount": "-200.00"
            }
          ]
        },
        {
          "ledgername": "Kotak Bank",
          "isdeemedpositive": false,
          "ispartyledger": true,
          "amount": "200.00",
          "bankallocations": [
            {
              "date": "20250831",
              "instrumentdate": "20250831",
              "email": "a@gmail.com",
              "transactiontype": "Inter Bank Transfer",
              "ifscode": "KKBK0000431",
              "bankname": "Kotak Mahindra Bank (India)",
              "accountnumber": "4891289138912",
              "paymentfavouring": "Akshaya Enterprises",
              "transactionname": "Primary",
              "transfermode": "NEFT",
              "bankid": "10",
              "instrumentnumber": "100",
              "paymentmode": "Transacted",
              "bankpartyname": "Akshaya Enterprises",
              "amount": "200.00"
            }
          ]
        }
      ]
    }
  ]
}
```

## Template 32

```json
{
  "static_variables": [
    {
      "name": "svVchImportFormat",
      "value": "jsonex"
    },
    {
      "name": "svCurrentCompany",
      "value": "Bhrama Enterprises"
    }
  ],
  "tallymessage": [
    {
      "metadata": {
        "type": "Voucher",
        "vchtype": "Payment",
        "action": "Create",
        "objview": "Accounting Voucher View"
      },
      "date": "20250831",
      "vouchertypename": "Payment",
      "partyledgername": "Cash",
      "persistedview": "Accounting Voucher View",
      "allledgerentries": [
        {
          "ledgername": "Sundry Expenses",
          "isdeemedpositive": true,
          "ispartyledger": false,
          "amount": "-100.00",
          "categoryallocations": [
            {
              "category": "Primary Cost Category",
              "isdeemedpositive": true,
              "costcentreallocations": [
                {
                  "name": "CostName",
                  "amount": "-100.00"
                }
              ]
            }
          ]
        },
        {
          "ledgername": "Cash",
          "isdeemedpositive": false,
          "ispartyledger": true,
          "amount": "100.00"
        }
      ]
    }
  ]
}
```

## Template 33

```json
{
  "static_variables": [
    {
      "name": "svVchImportFormat",
      "value": "jsonex"
    },
    {
      "name": "svCurrentCompany",
      "value": "Bhrama Enterprises"
    }
  ],
  "tallymessage": [
    {
      "metadata": {
        "type": "Voucher",
        "remoteid": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000095",
        "vchkey": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b348:00000058",
        "vchtype": "Payment",
        "action": "Alter",
        "objview": "Accounting Voucher View"
      },
      "date": "20250801",
      "guid": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000095"
    }
  ]
}
```

## Template 34

```json
{
  "static_variables": [
    {
      "name": "svVchImportFormat",
      "value": "jsonex"
    },
    {
      "name": "svCurrentCompany",
      "value": "Bhrama Enterprises"
    }
  ],
  "tallymessage": [
    {
      "metadata": {
        "type": "Voucher",
        "remoteid": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000095",
        "vchkey": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b348:00000058",
        "vchtype": "Payment",
        "action": "Delete",
        "objview": "Accounting Voucher View"
      },
      "guid": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000095"
    }
  ]
}
```

## Template 35

```json
{
  "static_variables": [
    {
      "name": "svExportFormat",
      "value": "jsonex"
    },
    {
      "name": "svCurrentCompany",
      "value": "Bhrama Enterprises"
    }
  ],
  "tdlmessage": [
    {
      "definitions": [
        {
          "metadata": {
            "name": "TSPL All Payment Vouchers",
            "type": "Collection"
          },
          "attributes": [
            {
              "Type": "Vouchers:VoucherType"
            },
            {
              "Child Of": "$$VchTypePayment"
            },
            {
              "Native Method": "Date, VoucherTypeName, VoucherNumber, partyledgername"
            }
          ]
        }
      ]
    }
  ]
}
```

## Template 36

```json
{
  "static_variables": [
    {
      "name": "svExportFormat",
      "value": "jsonex"
    },
    {
      "name": "svCurrentCompany",
      "value": "Bhrama Enterprises"
    }
  ],
  "tdlmessage": [
    {
      "definitions": [
        {
          "metadata": {
            "name": "TSPL Payment Vouchers",
            "type": "Collection"
          },
          "attributes": [
            {
              "Type": "Vouchers:VoucherType"
            },
            {
              "Child Of": "$$VchTypePayment"
            },
            {
              "Native Method": "Date, VoucherTypeName, VoucherNumber, partyledgername"
            },
            {
              "Filters": "Period Filter"
            }
          ]
        },
        {
          "metadata": {
            "name": "PeriodFilter",
            "type": "System",
            "sys_type": "Formulae",
            "ismodify": true
          },
          "value": "$Date >= $$Date:\"1-Apr-2025\" AND $Date <= $$Date:\"10-Apr-2025\"" 
        }
      ]
    }
  ]
}
```

## Template 37

```json
{
  "static_variables": [
    {
      "name": "svVchImportFormat",
      "value": "jsonex"
    },
    {
      "name": "svCurrentCompany",
      "value": "Bhrama Enterprises"
    }
  ],
  "tallymessage": [
    {
      "metadata": {
        "type": "Voucher",
        "vchtype": "Receipt",
        "action": "Create",
        "objview": "Accounting Voucher View"
      },
      "date": "20250831",
      "vouchertypename": "Receipt",
      "partyledgername": "ABC Party",
      "allledgerentries": [
        {
          "ledgername": "ABC Party",
          "isdeemedpositive": false,
          "ispartyledger": true,
          "amount": "2500.00"
        },
        {
          "ledgername": "Kotak Bank",
          "isdeemedpositive": true,
          "ispartyledger": true,
          "amount": "-2500.00",
          "bankallocations": [
            {
              "date": "20250831",
              "instrumentdate": "20250831",
              "transactiontype": "Cheque/DD",
              "bankname": "Kotak Mahindra Bank (India)",
              "paymentfavouring": "ABC Party",
              "instrumentnumber": "56465787",
              "paymentmode": "Transacted",
              "bankpartyname": "ABC Party",
              "amount": "-2500.00"
            }
          ]
        }
      ]
    }
  ]
}
```

## Template 38

```json
{
  "static_variables": [
    {
      "name": "svVchImportFormat",
      "value": "jsonex"
    },
    {
      "name": "svCurrentCompany",
      "value": "Bhrama Enterprises"
    }
  ],
  "tallymessage": [
    {
      "metadata": {
        "type": "Voucher",
        "vchtype": "Receipt",
        "action": "Create",
        "objview": "Accounting Voucher View"
      },
      "date": "20250831",
      "vouchertypename": "Receipt",
      "partyname": "Cash",
      "partyledgername": "Cash",
      "allledgerentries": [
        {
          "ledgername": "Income",
          "isdeemedpositive": false,
          "ispartyledger": false,
          "amount": "100.00",
          "categoryallocations": [
            {
              "category": "Primary Cost Category",
              "isdeemedpositive": false,
              "costcentreallocations": [
                {
                  "name": "CostName",
                  "amount": "100.00"
                }
              ]
            }
          ]
        },
        {
          "ledgername": "Cash",
          "isdeemedpositive": true,
          "ispartyledger": true,
          "amount": "-100.00"
        }
      ]
    }
  ]
}
```

## Template 39

```json
{
  "static_variables": [
    {
      "name": "svVchImportFormat",
      "value": "jsonex"
    },
    {
      "name": "svCurrentCompany",
      "value": "Bhrama Enterprises"
    }
  ],
  "tallymessage": [
    {
      "metadata": {
        "type": "Voucher",
        "vchtype": "Receipt",
        "remoteid": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000006d",
        "vchkey": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b34b:000000d0",
        "action": "Alter",
        "objview": "Accounting Voucher View"
      },
      "date": "20250801",
      "guid": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000006d"
    }
  ]
}
```

## Template 40

```json
{
  "static_variables": [
    {
      "name": "svVchImportFormat",
      "value": "jsonex"
    },
    {
      "name": "svCurrentCompany",
      "value": "Bhrama Enterprises"
    }
  ],
  "tallymessage": [
    {
      "metadata": {
        "type": "Voucher",
        "vchtype": "Receipt",
        "remoteid": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000006d",
        "vchkey": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b34b:000000d0",
        "action": "Delete",
        "objview": "Accounting Voucher View"
      },
      "guid": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000006d"
    }
  ]
}
```

## Template 41

```json
{
  "static_variables": [
    {
      "name": "svExportFormat",
      "value": "jsonex"
    },
    {
      "name": "svCurrentCompany",
      "value": "Bhrama Enterprises"
    }
  ],
  "tdlmessage": [
    {
      "definitions": [
        {
          "metadata": {
            "name": "TSPL All Receipt Vouchers",
            "type": "Collection"
          },
          "attributes": [
            {
              "Type": "Vouchers:VoucherType"
            },
            {
              "Child Of": "$$VchTypeReceipt"
            },
            {
              "Native Method": "Date, VoucherTypeName, VoucherNumber, Partyledgername"
            }
          ]
        }
      ]
    }
  ]
}
```

## Template 42

```json
{
  "static_variables": [
    {
      "name": "svExportFormat",
      "value": "jsonex"
    },
    {
      "name": "svCurrentCompany",
      "value": "Bhrama Enterprises"
    }
  ],
  "tdlmessage": [
    {
      "definitions": [
        {
          "metadata": {
            "name": "TSPL Receipt Vouchers",
            "type": "Collection"
          },
          "attributes": [
            {
              "Type": "Vouchers:VoucherType"
            },
            {
              "Child Of": "$$VchTypeReceipt"
            },
            {
              "Native Method": "Date, VoucherTypeName, VoucherNumber, Partyledgername"
            },
            {
              "Filters": "Period Filter"
            }
          ]
        },
        {
          "metadata": {
            "name": "PeriodFilter",
            "type": "System",
            "sys_type": "Formulae",
            "ismodify": true
          },
          "value": "$Date >= ($$Date:\"01-07-2025\") AND $Date <= ($$Date:\"10-07-2025\")"
        }
      ]
    }
  ]
}
```

## Template 43

```json
{
  "static_variables": [
    {
      "name": "svVchImportFormat",
      "value": "jsonex"
    },
    {
      "name": "svCurrentCompany",
      "value": "Bhrama Enterprises"
    }
  ],
  "tallymessage": [
    {
      "metadata": {
        "type": "Voucher",
        "vchtype": "Sales",
        "action": "Create",
        "objview": "Invoice Voucher View"
      },
      "date": "20250831",
      "vouchertypename": "Sales",
      "partyname": "Amar Enterprises",
      "partyledgername": "Amar Enterprises",
      "allinventoryentries": [
        {
          "stockitemname": "Coffee Powder",
          "isdeemedpositive": false,
          "rate": "2.00/nos",
          "amount": "40.00",
          "actualqty": " 20 nos",
          "billedqty": " 20 nos",
          "batchallocations": [
            {
              "godownname": "Main Location",
              "batchname": "Primary Batch",
              "destinationgodownname": "Main Location",
              "trackingnumber": "T001",
              "amount": "40.00",
              "actualqty": " 20 nos",
              "billedqty": " 20 nos"
            }
          ],
          "accountingallocations": [
            {
              "oldauditentryids": [
                {
                  "metadata": true,
                  "type": "Number"
                },
                "-1"
              ],
              "ledgername": "Sales",
              "isdeemedpositive": false,
              "ispartyledger": false,
              "amount": "40.00"
            }
          ]
        }
      ],
      "ledgerentries": [
        {
          "oldauditentryids": [
            {
              "metadata": true,
              "type": "Number"
            },
            "-1"
          ],
          "ledgername": "Amar Enterprises",
          "isdeemedpositive": true,
          "ispartyledger": true,
          "amount": "-40.00",
          "billallocations": [
            {
              "name": "12",
              "billtype": "New Ref",
              "amount": "-40.00"
            }
          ]
        }
      ]
    }
  ]
}
```

## Template 44

```json
{
  "static_variables": [
    {
      "name": "svVchImportFormat",
      "value": "jsonex"
    },
    {
      "name": "svCurrentCompany",
      "value": "Bhrama Enterprises"
    }
  ],
  "tallymessage": [
    {
      "metadata": {
        "type": "Voucher",
        "vchtype": "Sales",
        "action": "Create",
        "objview": "Invoice Voucher View"
      },
      "date": "20260301",
      "vchstatusdate": "20260301",
      "gstregistrationtype": "Regular",
      "statename": "Karnataka",
      "countryofresidence": "India",
      "partygstin": "29AAACH1004N1ZQ",
      "placeofsupply": "Karnataka",
      "vouchertypename": "Sales",
      "partyname": "Chanda Enterprises",
      "gstregistration": {
        "value": "Karnataka Registration",
        "taxtype": "GST",
        "taxregistration": "29AAECP4424C1ZN"
      },
      "cmpgstin": "29AAECP4424C1ZN",
      "partyledgername": "Chanda Enterprises",
      "basicbuyername": "Chanda Enterprises",
      "cmpgstregistrationtype": "Regular",
      "partymailingname": "Chanda Enterprises",
      "dispatchfromname": "Bhrama Enterprises",
      "dispatchfromstatename": "Karnataka",
      "consigneegstin": "29AAACH1004N1ZQ",
      "consigneemailingname": "Chanda Enterprises",
      "consigneestatename": "Karnataka",
      "cmpgststate": "Karnataka",
      "consigneecountryname": "India",
      "basicbasepartyname": "Chanda Enterprises",
      "effectivedate": "20260301",
      "isinvoice": true,
      "allinventoryentries": [
        {
          "stockitemname": "GST Coffee",
          "gstovrdnisrevchargeappl": "\\u0004 Not Applicable",
          "gstovrdntaxability": "Taxable",
          "gstsourcetype": "Stock Item",
          "gstitemsource": "GST Coffee",
          "hsnsourcetype": "Stock Item",
          "hsnitemsource": "GST Coffee",
          "gstovrdntypeofsupply": "Goods",
          "gstrateinferapplicability": "As per Masters/Company",
          "gsthsnname": "4820",
          "gsthsninferapplicability": "As per Masters/Company",
          "isdeemedpositive": false,
          "rate": "75.00/nos",
          "amount": "1500.00",
          "actualqty": " 20 nos",
          "billedqty": " 20 nos",
          "batchallocations": [
            {
              "godownname": "Main Location",
              "batchname": "Primary Batch",
              "amount": "1500.00",
              "actualqty": " 20 nos",
              "billedqty": " 20 nos"
            }
          ],
          "accountingallocations": [
            {
              "ledgername": "GST Sales",
              "isdeemedpositive": false,
              "ispartyledger": false,
              "amount": "1500.00"
            }
          ],
          "ratedetails": [
            {
              "gstratedutyhead": "CGST",
              "gstratevaluationtype": "Based on Value",
              "gstrate": " 2.50"
            },
            {
              "gstratedutyhead": "SGST/UTGST",
              "gstratevaluationtype": "Based on Value",
              "gstrate": " 2.50"
            },
            {
              "gstratedutyhead": "IGST",
              "gstratevaluationtype": "Based on Value",
              "gstrate": " 5"
            },
            {
              "gstratedutyhead": "Cess",
              "gstratevaluationtype": "\\u0004 Not Applicable"
            },
            {
              "gstratedutyhead": "State Cess",
              "gstratevaluationtype": "Based on Value"
            }
          ]
        }
      ],
      "ledgerentries": [
        {
          "ledgername": "Chanda Enterprises",
          "isdeemedpositive": true,
          "ispartyledger": true,
          "amount": "-1575.00",
          "billallocations": [
            {
              "name": "22",
              "billtype": "New Ref",
              "tdsdeducteeisspecialrate": false,
              "amount": "-1575.00"
            }
          ]
        },
        {
          "ledgername": "CGST",
          "isdeemedpositive": false,
          "ispartyledger": false,
          "amount": "37.50"
        },
        {
          "ledgername": "SGST",
          "isdeemedpositive": false,
          "ispartyledger": false,
          "amount": "37.50"
        }
      ]
    }
  ]
}
```

## Template 45

```json
{
  "static_variables": [
    {
      "name": "svVchImportFormat",
      "value": "jsonex"
    },
    {
      "name": "svCurrentCompany",
      "value": "Bhrama Enterprises"
    }
  ],
  "tallymessage": [
    {
      "metadata": {
        "type": "Voucher",
        "vchtype": "Sales",
        "remoteid": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000055",
        "vchkey": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b34b:00000088",
        "action": "Alter",
        "objview": "Invoice Voucher View"
      },
      "date": "20250801",
      "guid": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000055",
      "vouchertypename": "Sales"
    }
  ]
}
```

## Template 46

```json
{
  "static_variables": [
    {
      "name": "svVchImportFormat",
      "value": "jsonex"
    },
    {
      "name": "svCurrentCompany",
      "value": "Bhrama Enterprises"
    }
  ],
  "tallymessage": [
    {
      "metadata": {
        "type": "Voucher",
        "vchtype": "Sales",
        "remoteid": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000055",
        "vchkey": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b34b:00000088",
        "action": "Delete",
        "objview": "Invoice Voucher View"
      },
      "guid": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000055"
    }
  ]
}
```

## Template 47

```json
{
  "static_variables": [
    {
      "name": "svExportFormat",
      "value": "jsonex"
    },
    {
      "name": "svCurrentCompany",
      "value": "Bhrama Enterprises"
    }
  ],
  "tdlmessage": [
    {
      "definitions": [
        {
          "metadata": {
            "name": "TSPL All Sales Vouchers",
            "type": "Collection"
          },
          "attributes": [
            {
              "Type": "Vouchers:VoucherType"
            },
            {
              "Child Of": "$$VchTypeSales"
            },
            {
              "Native Method": "Date, VoucherTypeName, VoucherNumber, Partyledgername"
            }
          ]
        }
      ]
    }
  ]
}
```

## Template 48

```json
{
  "static_variables": [
    {
      "name": "svExportFormat",
      "value": "jsonex"
    },
    {
      "name": "svCurrentCompany",
      "value": "Bhrama Enterprises"
    }
  ],
  "tdlmessage": [
    {
      "definitions": [
        {
          "metadata": {
            "name": "TSPL Sales Vouchers",
            "type": "Collection"
          },
          "attributes": [
            {
              "Type": "Vouchers:VoucherType"
            },
            {
              "Child Of": "$$VchTypeSales"
            },
            {
              "Native Method": "Date, VoucherTypeName, VoucherNumber, Partyledgername"
            },
            {
              "Filters": "Period Filter"
            }
          ]
        },
        {
          "metadata": {
            "name": "PeriodFilter",
            "type": "System",
            "sys_type": "Formulae",
            "ismodify": true
          },
          "value": "$Date >= ($$Date:\"01-05-2025\") AND $Date <= ($$Date:\"10-05-2025\")"
        }
      ]
    }
  ]
}
```

## Template 49

```json
{
  "tallymessage": [
    {
      "metadata": {
        "type": "Voucher",
        "vchtype": "Purchase",
        "action": "Create",
        "objview": "Invoice Voucher View"
      },
      "date": "20260301",
      "vchstatusdate": "20260301",
      "gstregistrationtype": "\\u0004 Unknown",
      "statename": "Alabama",
      "countryofresidence": "United States of America",
      "vouchertypename": "Purchase",
      "partyname": "International Party",
      "partyledgername": "International Party",
      "basicbuyername": "Bhrama Enterprises",
      "cmpgstregistrationtype": "Regular",
      "partymailingname": "International Party",
      "consigneegstin": "29AAECP4424C1ZN",
      "consigneemailingname": "Bhrama Enterprises",
      "consigneestatename": "Karnataka",
      "cmpgststate": "Karnataka",
      "consigneecountryname": "India",
      "basicbasepartyname": "International Party",
      "effectivedate": "20260301",
      "isinvoice": true,
      "allinventoryentries": [
        {
          "stockitemname": "Computer US",
          "isdeemedpositive": true,
          "rate": "10000.00/nos",
          "amount": "-200000.00",
          "actualqty": " 20 nos",
          "billedqty": " 20 nos",
          "batchallocations": [
            {
              "godownname": "Main Location",
              "batchname": "Primary Batch",
              "amount": "-200000.00",
              "actualqty": " 20 nos",
              "billedqty": " 20 nos"
            }
          ],
          "accountingallocations": [
            {
              "ledgername": "Purchase",
              "isdeemedpositive": true,
              "ispartyledger": false,
              "amount": "-200000.00"
            }
          ]
        }
      ],
      "ledgerentries": [
        {
          "ledgername": "International Party",
          "isdeemedpositive": false,
          "ispartyledger": true,
          "amount": "200000.00",
          "billallocations": [
            {
              "name": "12",
              "billtype": "New Ref",
              "amount": "200000.00"
            }
          ]
        }
      ]
    }
  ]
}
```

## Template 50

```json
{
  "static_variables": [
    {
      "name": "svVchImportFormat",
      "value": "jsonex"
    },
    {
      "name": "svCurrentCompany",
      "value": "Bhrama Enterprises"
    }
  ],
  "tallymessage": [
    {
      "metadata": {
        "type": "Voucher",
        "vchtype": "Purchase",
        "action": "Create",
        "objview": "Invoice Voucher View"
      },
      "date": "20250901",
      "vchstatusdate": "20250901",
      "gstregistrationtype": "Regular",
      "vatdealertype": "Regular",
      "statename": "Karnataka",
      "countryofresidence": "India",
      "partygstin": "29AAACH1004N1ZQ",
      "placeofsupply": "Karnataka",
      "vouchertypename": "Purchase",
      "partyname": "Mondal Enterprises",
      "gstregistration": {
        "value": "Karnataka Registration",
        "taxtype": "GST",
        "taxregistration": "29AAECP4424C1ZN"
      },
      "cmpgstin": "29AAECP4424C1ZN",
      "partyledgername": "Mondal Enterprises",
      "basicbuyername": "Bhrama Enterprises",
      "cmpgstregistrationtype": "Regular",
      "partymailingname": "Mondal Enterprises",
      "consigneegstin": "29AAECP4424C1ZN",
      "consigneemailingname": "Bhrama Enterprises",
      "consigneestatename": "Karnataka",
      "cmpgststate": "Karnataka",
      "consigneecountryname": "India",
      "basicbasepartyname": "Mondal Enterprises",
      "effectivedate": "20250901",
      "isinvoice": true,
      "allinventoryentries": [
        {
          "stockitemname": "Decaf Coffee",
          "gstovrdnineligibleitc": "\\u0004 Not Applicable",
          "gstovrdnisrevchargeappl": "\\u0004 Not Applicable",
          "gstovrdntaxability": "Taxable",
          "gstsourcetype": "Stock Item",
          "gstitemsource": "Decaf Coffee",
          "hsnsourcetype": "Stock Item",
          "hsnitemsource": "Decaf Coffee",
          "gstovrdntypeofsupply": "Goods",
          "gstrateinferapplicability": "As per Masters/Company",
          "gsthsninferapplicability": "As per Masters/Company",
          "isdeemedpositive": true,
          "rate": "15.00/nos",
          "amount": "-1500.00",
          "actualqty": " 100 nos",
          "billedqty": " 100 nos",
          "batchallocations": [
            {
              "godownname": "Main Location",
              "batchname": "Primary Batch",
              "amount": "-1500.00",
              "actualqty": " 100 nos",
              "billedqty": " 100 nos"
            }
          ],
          "accountingallocations": [
            {
              "ledgername": "GST Purchase",
              "isdeemedpositive": true,
              "ispartyledger": false,
              "amount": "-1500.00"
            }
          ],
          "ratedetails": [
            {
              "gstratedutyhead": "CGST",
              "gstratevaluationtype": "Based on Value",
              "gstrate": " 2"
            },
            {
              "gstratedutyhead": "SGST/UTGST",
              "gstratevaluationtype": "Based on Value",
              "gstrate": " 2"
            },
            {
              "gstratedutyhead": "IGST",
              "gstratevaluationtype": "Based on Value",
              "gstrate": " 4"
            },
            {
              "gstratedutyhead": "Cess",
              "gstratevaluationtype": "\\u0004 Not Applicable"
            },
            {
              "gstratedutyhead": "State Cess",
              "gstratevaluationtype": "Based on Value"
            }
          ]
        }
      ],
      "ledgerentries": [
        {
          "ledgername": "Mondal Enterprises",
          "isdeemedpositive": false,
          "ispartyledger": true,
          "amount": "1560.00",
          "billallocations": [
            {
              "name": "46",
              "billtype": "New Ref",
              "amount": "1560.00"
            }
          ]
        },
        {
          "ledgername": "CGST",
          "isdeemedpositive": true,
          "ispartyledger": false,
          "amount": "-30.00"
        },
        {
          "ledgername": "SGST",
          "isdeemedpositive": true,
          "ispartyledger": false,
          "amount": "-30.00"
        }
      ]
    }
  ]
}
```

## Template 51

```json
{
  "static_variables": [
    {
      "name": "svVchImportFormat",
      "value": "jsonex"
    },
    {
      "name": "svCurrentCompany",
      "value": "Bhrama Enterprises"
    }
  ],
  "tallymessage": [
    {
      "metadata": {
        "type": "Voucher",
        "vchtype": "Purchase",
        "remoteid": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000075",
        "vchkey": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b34b:000000f8",
        "action": "Alter",
        "objview": "Invoice Voucher View"
      },
      "date": "20250802",
      "effectivedate": "20250802",
      "guid": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000075"
    }
  ]
}
```

## Template 52

```json
{
  "static_variables": [
    {
      "name": "svVchImportFormat",
      "value": "jsonex"
    },
    {
      "name": "svCurrentCompany",
      "value": "Bhrama Enterprises"
    }
  ],
  "tallymessage": [
    {
      "metadata": {
        "type": "Voucher",
        "vchtype": "Purchase",
        "remoteid": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000083",
        "vchkey": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b400:00000010",
        "action": "Delete",
        "objview": "Invoice Voucher View"
      },
      "guid": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000083"
    }
  ]
}
```

## Template 53

```json
{
  "static_variables": [
    {
      "name": "svExportFormat",
      "value": "jsonex"
    },
    {
      "name": "svCurrentCompany",
      "value": "Bhrama Enterprises"
    }
  ],
  "tdlmessage": [
    {
      "definitions": [
        {
          "metadata": {
            "name": "TSPL All Purchase Vouchers",
            "type": "Collection"
          },
          "attributes": [
            {
              "Type": "Vouchers:VoucherType"
            },
            {
              "Child Of": "$$VchTypePurchase"
            },
            {
              "Native Method": "Date, VoucherTypeName, VoucherNumber, Partyledgername"
            }
          ]
        }
      ]
    }
  ]
}
```

## Template 54

```json
{
  "static_variables": [
    {
      "name": "svExportFormat",
      "value": "jsonex"
    },
    {
      "name": "svCurrentCompany",
      "value": "Bhrama Enterprises"
    }
  ],
  "tdlmessage": [
    {
      "definitions": [
        {
          "metadata": {
            "name": "TSPL Purchase Vouchers",
            "type": "Collection"
          },
          "attributes": [
            {
              "Type": "Vouchers:VoucherType"
            },
            {
              "Child Of": "$$VchTypePurchase"
            },
            {
              "Native Method": "Date, VoucherTypeName, VoucherNumber, Partyledgername"
            },
            {
              "Filters": "Period Filter"
            }
          ]
        },
        {
          "metadata": {
            "name": "PeriodFilter",
            "type": "System",
            "sys_type": "Formulae",
            "ismodify": true
          },
          "value": "$Date >= ($$Date:\"01-07-2025\") AND $Date <= ($$Date:\"10-07-2025\")"
        }
      ]
    }
  ]
}
```

## Template 55

```json
{
  "static_variables": [
    {
      "name": "svExportFormat",
      "value": "jsonex"
    },
    {
      "name": "svCurrentCompany",
      "value": "Bhrama Enterprises"
    },
    {
      "name": "svFromDate",
      "value": "20250401"
    },
    {
      "name": "svToDate",
      "value": "20250430"
    }
  ]
}
```

## Template 56

```json
{
  "static_variables": [
    {
      "name": "svExportFormat",
      "value": "jsonex"
    },
    {
      "name": "svCurrentCompany",
      "value": "Bhrama Enterprises"
    },
    {
      "name": "svFromDate",
      "value": "20250401"
    },
    {
      "name": "svToDate",
      "value": "20250430"
    },
    {
      "name": "ExplodeFlag",
      "value": "Yes"
    },
    {
      "name": "ExplodeAllLevels",
      "value": "Yes"
    }
  ]
}
```

## Template 57

```json
{
  "static_variables": [
    {
      "name": "svExportFormat",
      "value": "jsonex"
    },
    {
      "name": "svCurrentCompany",
      "value": "Bhrama Enterprises"
    },
    {
      "name": "svFromDate",
      "value": "20250401"
    },
    {
      "name": "svToDate",
      "value": "20250430"
    }
  ],
  "tdlmessage": [
    {
      "definitions": [
        {
          "metadata": {
            "name": "Trial Balance",
            "type": "Report",
            "ismodify": true
          },
          "attributes": [
            {
              "Plain Xml": "Yes"
            }
          ]
        }
      ]
    }
  ]
}
```

## Template 58

```json
{
  "static_variables": [
    {
      "name": "svExportFormat",
      "value": "jsonex"
    },
    {
      "name": "svCurrentCompany",
      "value": "Bhrama Enterprises"
    },
    {
      "name": "svFromDate",
      "value": "20250401"
    },
    {
      "name": "svToDate",
      "value": "20250430"
    }
  ],
  "tdlmessage": [
    {
      "definitions": [
        {
          "metadata": {
            "name": "Trial Balance",
            "type": "Report",
            "ismodify": true
          },
          "attributes": [
            {
              "Export Empty Fields": "Yes"
            }
          ]
        }
      ]
    }
  ]
}
```

## Template 59

```json
{
  "static_variables": [
    {
      "name": "svExportFormat",
      "value": "jsonex"
    },
    {
      "name": "svCurrentCompany",
      "value": "Bhrama Enterprises"
    },
    {
      "name": "svFromDate",
      "value": "20250401"
    },
    {
      "name": "svToDate",
      "value": "20250430"
    },
    {
      "name": "IsLedgerwise",
      "value": "Yes"
    }
  ]
}
```

## Template 60

```json
{
  "static_variables": [
    {
      "name": "svExportFormat",
      "value": "jsonex"
    },
    {
      "name": "svCurrentCompany",
      "value": "Bhrama Enterprises"
    },
    {
      "name": "svFromDate",
      "value": "20250401"
    },
    {
      "name": "svToDate",
      "value": "20250430"
    }
  ],
  "tdlmessage": [
    {
      "definitions": [
        {
          "metadata": {
            "name": "Trial Balance",
            "type": "Report",
            "ismodify": true
          },
          "attributes": [
            {
              "Set": "Groupname :\"Bank Accounts\""
            }
          ]
        }
      ]
    }
  ]
}
```

## Template 61

```json
{
  "static_variables": [
    {
      "name": "svExportFormat",
      "value": "jsonex"
    },
    {
      "name": "svCurrentCompany",
      "value": "Bhrama Enterprises"
    },
    {
      "name": "svFromDate",
      "value": "20250401"
    },
    {
      "name": "svToDate",
      "value": "20260331"
    }
  ]
}
```

## Template 62

```json
{
  "static_variables": [
    {
      "name": "svExportFormat",
      "value": "jsonex"
    },
    {
      "name": "svCurrentCompany",
      "value": "Bhrama Enterprises"
    },
    {
      "name": "svFromDate",
      "value": "20250401"
    },
    {
      "name": "svToDate",
      "value": "20260331"
    }
  ],
  "tdlmessage": [
    {
      "definitions": [
        {
          "metadata": {
            "name": "Sales Register",
            "type": "Report",
            "ismodify": true
          },
          "attributes": [
            {
              "Plain Xml": "Yes"
            }
          ]
        }
      ]
    }
  ]
}
```

## Template 63

```json
{
  "static_variables": [
    {
      "name": "svExportFormat",
      "value": "jsonex"
    },
    {
      "name": "svCurrentCompany",
      "value": "Bhrama Enterprises"
    },
    {
      "name": "svFromDate",
      "value": "20250401"
    },
    {
      "name": "svToDate",
      "value": "20260331"
    }
  ],
  "tdlmessage": [
    {
      "definitions": [
        {
          "metadata": {
            "name": "Sales Register",
            "type": "Report",
            "ismodify": true
          },
          "attributes": [
            {
              "Export Empty Fields": "Yes"
            }
          ]
        }
      ]
    }
  ]
}
```

## Template 64

```json
{
  "static_variables": [
    { "name": "svExportFormat", "value": "$$SysName:jsonex" },
    { "name": "svCurrentCompany", "value": "Bhrama Enterprises" }
  ],
  "tallymessage": [
    {
      "ledger": {
        "name": "SADE Pvt Ltd",
        "parent": "Sundry Debtors",
        "openingbalance": "0"
      }
    }
  ]
}
```

## Template 65

```json
{
  "static_variables": [
    { "name": "svExportFormat", "value": "$$SysName:jsonex" },
    { "name": "svCurrentCompany", "value": "Bhrama Enterprises" }
  ],
  "tallymessage": [
    {
      "ledger": {
        "name": "Kotak Bank",
        "parent": "Bank Accounts",
        "openingbalance": "0"
      }
    }
  ]
}
```

## Template 66

```json
{
  "static_variables": [
    { "name": "svExportFormat", "value": "$$SysName:jsonex" },
    { "name": "svCurrentCompany", "value": "Bhrama Enterprises" }
  ],
  "tallymessage": [
    {
      "ledger": {
        "name": "SADE Pvt Ltd",
        "action": "Alter",
        "openingbalance": "75000"
      }
    }
  ]
}
```

## Template 67

```json
{
  "static_variables": [
    { "name": "svExportFormat", "value": "$$SysName:jsonex" },
    { "name": "svCurrentCompany", "value": "Bhrama Enterprises" }
  ],
  "tallymessage": [
    {
      "ledger": {
        "name": "Kotak Bank",
        "action": "Alter",
        "parent": "Bank Accounts"
      }
    }
  ]
}
```

## Template 68

```json
{
  "static_variables": [
    { "name": "svExportFormat", "value": "$$SysName:jsonex" },
    { "name": "svCurrentCompany", "value": "Bhrama Enterprises" }
  ],
  "tallymessage": [
    {
      "ledger": {
        "name": "SADE Pvt Ltd",
        "action": "Delete"
      }
    }
  ]
}
```

## Template 69

```json
{
  "static_variables": [
    { "name": "svExportFormat", "value": "$$SysName:jsonex" },
    { "name": "svCurrentCompany", "value": "Bhrama Enterprises" },
    { "name": "LedgerName", "value": "Cash" }
  ]
}
```

