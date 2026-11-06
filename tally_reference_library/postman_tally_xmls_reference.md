# Tally XMLS for Integration with Third-Party Apps (Postman Reference)

- **Source URL:** https://documenter.getpostman.com/view/13855108/TzeRpAMt
- **Raw API Endpoint:** `https://documenter.gw.postman.com/api/collections/13855108/TzeRpAMt?segregateAuth=true&versionTag=latest`
- **Collection ID:** `9530b1ce-7099-4886-b0d9-5cf7970c1151` (`TzeRpAMt`)
- **Author / Generator:** Sai Vineeth — [TallyConnector](https://github.com/Accounting-Companion/TallyConnector) / [TallyXmlsGenerator](https://github.com/Accounting-Companion/TallyXmlsGenerator)
- **Published Date:** `2021-06-11T07:11:16.000Z`
- **Collection Variables:**
  - `TallyURL`: `http://localhost`
  - `TallyPort`: `9000`

---

## 1. Original Collection Description

> When Developing [Tally Connector Library](https://github.com/Accounting-Companion/TallyConnector), I did some research to get data from Tally in easier way using XML API and found these xmls useful.
> Following are the Xml Requests To Communicate with Tally Prime/ Tally ERP 9.

---

## 2. Critical Architectural Learnings (Why Memory Access Violations Happen & How TallyConnector Avoids Them)

### 2.1 Mandatory TDL Definition Attributes (`ISMODIFY`, `ISFIXED`, `ISINITIALIZE`, `ISOPTION`, `ISINTERNAL`)
Every single `<COLLECTION>`, `<REPORT>`, `<FORM>`, `<PART>`, `<LINE>`, `<FIELD>`, and `<FUNCTION>` tag in this repository explicitly sets all five TDL object flags:
```xml
ISMODIFY="No" ISFIXED="No" ISINITIALIZE="No" ISOPTION="No" ISINTERNAL="No"
```
*(Except `GetActiveCompany` which uses `ISINITIALIZE="Yes"` on `CUSTOMCOMPANYCOL`, and option forms/lines which use `ISOPTION="Yes"`).*
- **Why this matters:** In TallyPrime (especially 6.1 Edit Log and Tally.ERP 9), omitting these attributes on ad-hoc TDL definitions sent over HTTP leaves internal C++ struct flags uninitialized in Tally's TDL interpreter, causing immediate **Memory Access Violations (MAV)**.

### 2.2 Voucher Collection Export Pattern (`<BELONGSTO>Yes</BELONGSTO>` & `<NATIVEMETHOD>*, *.*</NATIVEMETHOD>`)
When exporting vouchers by voucher type (`<TYPE>Vouchers : VoucherType</TYPE>`):
1. `<SVFROMDATE TYPE="Date">01-04-2022</SVFROMDATE>` and `<SVTODATE TYPE="Date">31-03-2023</SVTODATE>` **must** carry `TYPE="Date"` and use `DD-MM-YYYY` format.
2. The collection **must** include `<BELONGSTO>Yes</BELONGSTO>` so Tally includes vouchers belonging to child voucher types derived from the base type.
3. Instead of fragile nested dot-paths in `<NATIVEMETHOD>` (like `AllLedgerEntries.BillAllocations.Name` which can crash Tally's XML serializer with MAV), TallyConnector uses:
   ```xml
   <NATIVEMETHOD>*, *.*</NATIVEMETHOD>
   ```
   or lets Tally export default native methods cleanly.

### 2.3 Safe Version & License Probing (`LicenseInfo` Report vs. `Company` Collection)
Injecting `<COMPUTE>ProductVersion: $$ProductVersion</COMPUTE>` inside a `<TYPE>Company</TYPE>` collection causes a Memory Access Violation because `$$ProductVersion` is not a valid TDL function in that context.
Instead, TallyConnector uses a dedicated `<TYPE>DATA</TYPE>` report (`<ID>LicenseInfo</ID>`) with `<FIELD>` definitions using system formulas (`@@CapProductDetails`, `@@VersionReleaseString`, `$$LicenseInfo:SerialNumber`, etc.) to safely extract `TALLYVERSION`, `SERIALNUMBER`, `PLANNAME`, `DATAPATH`, and `APPLICATIONPATH`.

### 2.4 Active Company Discovery (`GetActiveCompany`)
Instead of `TYPE=Object, SUBTYPE=Company` (which is a TallyPrime 7.0 JSON API feature that causes MAV in older XML engines), TallyConnector queries `<TYPE>COMPANY</TYPE>` with explicit `<NATIVEMETHOD>` tags:
```xml
<COLLECTION ISMODIFY="No" ISFIXED="No" ISINITIALIZE="Yes" ISOPTION="No" ISINTERNAL="No" NAME="CUSTOMCOMPANYCOL">
  <TYPE>COMPANY</TYPE>
  <NATIVEMETHOD>NAME</NATIVEMETHOD>
  <NATIVEMETHOD>GUID</NATIVEMETHOD>
  <NATIVEMETHOD>BOOKSFROM</NATIVEMETHOD>
  <NATIVEMETHOD>STARTINGFROM</NATIVEMETHOD>
  <NATIVEMETHOD>COMPANYNUMBER</NATIVEMETHOD>
  <NATIVEMETHOD>ENDINGAT</NATIVEMETHOD>
  <FILTERS>ActiveCompFilt</FILTERS>
</COLLECTION>
<SYSTEM TYPE="Formulae" NAME="ActiveCompFilt">$Name = ##SVCURRENTCOMPANY</SYSTEM>
```
*(Or without `<FILTERS>` to list all open companies with full metadata in a single query!)*

### 2.5 Cost Centres, Employee Groups, and Employees Share `<TYPE>COSTCENTRE</TYPE>`
In Tally's internal database schema, Cost Centres, Employee Groups, and Employees are all stored in the `COSTCENTRE` table and distinguished by two boolean flags (`$ISEMPLOYEEGROUP` and `$FORPAYROLL`):
- **Cost Centres:** `Not $ISEMPLOYEEGROUP` AND `Not $FORPAYROLL`
- **Employee Groups:** `$ISEMPLOYEEGROUP`
- **Employees:** `Not $ISEMPLOYEEGROUP` AND `$FORPAYROLL`
*(Note: In the Postman collection, the `EmployeeGroups` and `Employees` requests were accidentally pasted with the same filter as `CostCentres`, demonstrating how TallyConnector's generator templates them from `COSTCENTRE` with those two filter predicates).*

### 2.6 Instant Count & Deletion Detection Reports (`Stats_Master`, `Stats_Voucher`, `TC_AutoColumnStats`)
The `Export -> Reports` folder provides three extraordinary TDL reports that are critical for fast reconciliation and deletion detection:
1. **`Stats_Master` (`MasterTypeStat`):** Repeats over `STATObjects` (`$NAME`, `$StatVal`) to return the exact live count of every master entity type in Tally in a single lightweight call!
2. **`Stats_Voucher` (`VoucherTypeStat`):** Repeats over `STATVchType` (`$NAME`, `$StatVal`, `$CancVal`) to return the exact total count and cancelled count per Voucher Type for a date range!
3. **`TC_AutoColumnStats`:** Automatically buckets voucher counts, optional counts, and cancelled counts by month (`SVPeriodicity:"Month"`) across the entire date range in a single request!

---

## 3. Complete Folder & Request Index

1. **Export**
   - **Collections**
     - **VouchersByVoucherType** (18 requests)
       1. `Payment_Vouchers` (`$$VchTypePayment`)
       2. `ReceiptNote_Vouchers` [Receipt] (`$$VchTypeReceipt`)
       3. `Contra_Vouchers` (`$$VchTypeContra`)
       4. `Journal_Vouchers` (`$$VchTypeJournal`)
       5. `ReversingJournal_Vouchers` (`$$VchTypeRevJrnl`)
       6. `Sales_Vouchers` (`$$VchTypeSales`)
       7. `Purchase_Vouchers` (`$$VchTypePurchase`)
       8. `SalesOrder_Vouchers` (`$$VchTypeSalesOrder`)
       9. `PurchaseOrder_Vouchers` (`$$VchTypePurcOrder`)
       10. `DebitNote_Vouchers` (`$$VchTypeDebitNote`)
       11. `CreditNote_Vouchers` (`$$VchTypeCreditNote`)
       12. `JobWorkOut_Vouchers` (`$$VchTypeJobOrderIn`)
       13. `JobWorkIn_Vouchers` (`$$VchTypeJobOrderOut`)
       14. `MaterialIn_Vouchers` (`$$VchTypeJobMaterialReceive`)
       15. `MaterialOut_Vouchers` (`$$VchTypeJobMaterialIssue`)
       16. `Memo_Vouchers` (`$$VchTypeMemo`)
       17. `DeliveryNote_Vouchers` (`$$VchTypeDelNote`)
       18. `ReceiptNote_Vouchers` (`$$VchTypeRcptNote`)
       19. `StockJournal_Vouchers` (`$$VchTypeStockJrnl`)
       20. `PhysicalStock_Vouchers` (`$$VchTypePhysStock`)
       21. `RejectionsIn_Vouchers` (`$$VchTypeRejIn`)
       22. `RejectionsOut_Vouchers` (`$$VchTypeRejOut`)
       23. `Payroll_Vouchers` (`$$VchTypePayroll`)
       24. `Attendance_Vouchers` (`$$VchTypeAttendance`)
     - **Masters** (12 requests)
       1. `Currencies` (`CURRENCY`)
       2. `Groups` *(contains `TC_AutoColumnStats` report in Postman; standard `GROUP` collection follows `CUSTOMGROUPCOL` pattern)*
       3. `Ledgers` (`LEDGER`)
       4. `CostCategories` (`COSTCATEGORY`)
       5. `CostCentres` (`COSTCENTRE` with `IsEmployeeGroup` & `IsPayroll` filters)
       6. `StockCategories` (`STOCKCATEGORY`)
       7. `StockGroups` (`STOCKGROUP`)
       8. `StockItems` (`STOCKITEM`)
       9. `Units` (`UNIT`)
       10. `Godowns` (`GODOWN`)
       11. `VoucherTypes` (`VOUCHERTYPE`)
       12. `EmployeeGroups` (`COSTCENTRE` filtered for Employee Groups)
       13. `Employees` (`COSTCENTRE` filtered for Employees)
     - **Voucher** (1 request)
       1. `Voucher` (`CUSTOMVOUCHERCOL` -> `<TYPE>VOUCHER</TYPE>`)
   - **Reports** (3 requests)
     1. `Stats_Master` (`MasterTypeStat`)
     2. `Stats_Voucher` (`VoucherTypeStat`)
     3. `LicenseInfo` (`LicenseInfo`)
2. **Import**
   - **Masters -> Ledger** (2 requests)
     1. `BasicLedger`
     2. `LedgerwithOpeningBalance`
   - **Voucher** (4 requests)
     1. `basicVoucher`
     2. `basicInvoiceVoucher`
     3. `VoucherwithCostCenter`
     4. `InvoiceVoucherwithCostCenter`
3. **Root Requests**
   - `Test` (Empty ping)
   - `GetActiveCompany` (`CUSTOMCOMPANYCOL`)

---

## 4. Verbatim XML Payloads from the Repository

### 4.1 `Export / Collections / VouchersByVoucherType`

All 24 requests under `VouchersByVoucherType` use the following canonical structure, differing only in the `<CHILDOF>` system formula:

| Request Name | `<CHILDOF>` Value |
|---|---|
| `Payment_Vouchers` | `$$VchTypePayment` |
| `ReceiptNote_Vouchers` (Receipt) | `$$VchTypeReceipt` |
| `Contra_Vouchers` | `$$VchTypeContra` |
| `Journal_Vouchers` | `$$VchTypeJournal` |
| `ReversingJournal_Vouchers` | `$$VchTypeRevJrnl` |
| `Sales_Vouchers` | `$$VchTypeSales` |
| `Purchase_Vouchers` | `$$VchTypePurchase` |
| `SalesOrder_Vouchers` | `$$VchTypeSalesOrder` |
| `PurchaseOrder_Vouchers` | `$$VchTypePurcOrder` |
| `DebitNote_Vouchers` | `$$VchTypeDebitNote` |
| `CreditNote_Vouchers` | `$$VchTypeCreditNote` |
| `JobWorkOut_Vouchers` | `$$VchTypeJobOrderIn` |
| `JobWorkIn_Vouchers` | `$$VchTypeJobOrderOut` |
| `MaterialIn_Vouchers` | `$$VchTypeJobMaterialReceive` |
| `MaterialOut_Vouchers` | `$$VchTypeJobMaterialIssue` |
| `Memo_Vouchers` | `$$VchTypeMemo` |
| `DeliveryNote_Vouchers` | `$$VchTypeDelNote` |
| `ReceiptNote_Vouchers` (RcptNote) | `$$VchTypeRcptNote` |
| `StockJournal_Vouchers` | `$$VchTypeStockJrnl` |
| `PhysicalStock_Vouchers` | `$$VchTypePhysStock` |
| `RejectionsIn_Vouchers` | `$$VchTypeRejIn` |
| `RejectionsOut_Vouchers` | `$$VchTypeRejOut` |
| `Payroll_Vouchers` | `$$VchTypePayroll` |
| `Attendance_Vouchers` | `$$VchTypeAttendance` |

#### Template Payload (`VouchersByVoucherType`)
```xml
<!-- 
Generated Using TallyConnector - https://github.com/Accounting-Companion/TallyConnector
Incase of any errors raise a issue here - https://github.com/Accounting-Companion/TallyXmlsGenerator
--> 
<ENVELOPE Action="">
  <HEADER>
    <VERSION>1</VERSION>
    <TALLYREQUEST>EXPORT</TALLYREQUEST>
    <TYPE>COLLECTION</TYPE>
    <ID>CustomVoucherCollection</ID>
  </HEADER>
  <BODY>
    <DESC>
      <STATICVARIABLES>
        <SVCURRENTCOMPANY>ABC Company Ltd</SVCURRENTCOMPANY>
        <SVFROMDATE TYPE="Date">01-04-2022</SVFROMDATE>
        <SVTODATE TYPE="Date">31-03-2023</SVTODATE>
      </STATICVARIABLES>
      <TDL>
        <TDLMESSAGE>
          <COLLECTION ISMODIFY="No" ISFIXED="No" ISINITIALIZE="No" ISOPTION="No" ISINTERNAL="No" NAME="CustomVoucherCollection">
            <TYPE>Vouchers : VoucherType</TYPE>
            <CHILDOF>$$VchTypeSales</CHILDOF>
            <BELONGSTO>Yes</BELONGSTO>
            <NATIVEMETHOD>*, *.*</NATIVEMETHOD>
          </COLLECTION>
        </TDLMESSAGE>
      </TDL>
    </DESC>
  </BODY>
</ENVELOPE>
```

---

### 4.2 `Export / Collections / Masters`

#### 4.2.1 `Currencies`
```xml
<ENVELOPE Action="">
  <HEADER>
    <VERSION>1</VERSION>
    <TALLYREQUEST>EXPORT</TALLYREQUEST>
    <TYPE>COLLECTION</TYPE>
    <ID>CUSTOMCURRENCYCOL</ID>
  </HEADER>
  <BODY>
    <DESC>
      <STATICVARIABLES />
      <TDL>
        <TDLMESSAGE>
          <COLLECTION ISMODIFY="No" ISFIXED="No" ISINITIALIZE="No" ISOPTION="No" ISINTERNAL="No" NAME="CUSTOMCURRENCYCOL">
            <TYPE>CURRENCY</TYPE>
          </COLLECTION>
        </TDLMESSAGE>
      </TDL>
    </DESC>
  </BODY>
</ENVELOPE>
```

#### 4.2.2 `Groups` (Note: In Postman, this entry stores `TC_AutoColumnStats`; standard Group collection is `CUSTOMGROUPCOL` with `<TYPE>GROUP</TYPE>`)
```xml
<ENVELOPE Action="">
  <HEADER>
    <VERSION>1</VERSION>
    <TALLYREQUEST>EXPORT</TALLYREQUEST>
    <TYPE>COLLECTION</TYPE>
    <ID>CUSTOMGROUPCOL</ID>
  </HEADER>
  <BODY>
    <DESC>
      <STATICVARIABLES />
      <TDL>
        <TDLMESSAGE>
          <COLLECTION ISMODIFY="No" ISFIXED="No" ISINITIALIZE="No" ISOPTION="No" ISINTERNAL="No" NAME="CUSTOMGROUPCOL">
            <TYPE>GROUP</TYPE>
          </COLLECTION>
        </TDLMESSAGE>
      </TDL>
    </DESC>
  </BODY>
</ENVELOPE>
```

#### 4.2.3 `TC_AutoColumnStats` (Stored under `Groups` in Postman Collection)
```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>EXPORT</TALLYREQUEST>
        <TYPE>Data</TYPE>
        <ID>TC_AutoColumnStats</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
                <SVCURRENTCOMPANY>ABC Company Ltd</SVCURRENTCOMPANY>
                <SVFROMDATE TYPE= "Date">01-07-2010</SVFROMDATE>
                <SVTODATE TYPE= "Date">31-08-2010</SVTODATE>
            </STATICVARIABLES>
            <TDL>
                <TDLMESSAGE>
                    <REPORT NAME= "TC_AutoColumnStats" ISMODIFY= "No" ISFIXED= "No" ISINITIALIZE= "No"  ISOPTION= "No" ISINTERNAL= "No">
                        <FORMS>TC_AutoColumnStats</FORMS>
                        <VARIABLE>DoSetAutoColumn,SVPeriodicity,SVFromDate,SVToDate</VARIABLE>
                        <REPEAT> SVFromDate, SVToDate</REPEAT>
                        <SET>DoSetAutoColumn:Yes</SET>
                        <SET>SVPeriodicity:"Month"</SET>
                        <SET>DSPRepeatCollection:"Period Collection"</SET>
                    </REPORT>
                    <FORM NAME= "TC_AutoColumnStats" ISMODIFY= "No" ISFIXED= "No" ISINITIALIZE= "No"  ISOPTION= "No" ISINTERNAL= "No">
                        <TOPPARTS>TC_AutoColumnStats</TOPPARTS>
                        <OPTION>TC_SETAUTOOPTION:$$SetAutoColumns:SVFromDATE,SVTODATE</OPTION>
                    </FORM>
                    <FORM NAME= "TC_SETAUTOOPTION" ISMODIFY= "No" ISFIXED= "No" ISINITIALIZE= "No"  ISOPTION= "Yes" ISINTERNAL= "No">
                        <TOPPARTS />
                    </FORM>
                    <PART NAME= "TC_AutoColumnStats" ISMODIFY= "No" ISFIXED= "No" ISINITIALIZE= "No"  ISOPTION= "No" ISINTERNAL= "No">
                        <TOPLINES>TC_AutoColumnStats</TOPLINES>
                        <REPEAT>TC_AutoColumnStats : TC_VchTypeCollection</REPEAT>
                        <SCROLLED>Vertical</SCROLLED>
                    </PART>
                    <LINE NAME= "TC_AutoColumnStats" ISMODIFY= "No" ISFIXED= "No" ISINITIALIZE= "No"  ISOPTION= "No" ISINTERNAL= "No">
                        <FIELDS>TC_VchTypeName</FIELDS>
                        <FIELDS>TC_VchTypeTotalCount</FIELDS>
                        <XMLTAG>VchTypeStat</XMLTAG>
                        <OPTION>TC_AutoColumnStatsRepeat:$MigVal&gt;0</OPTION>
                    </LINE>
                    <LINE NAME= "TC_AutoColumnStatsRepeat" ISMODIFY= "No" ISFIXED= "No"  ISINITIALIZE= "No" ISOPTION= "Yes" ISINTERNAL= "No">
                        <FIELDS>TC_VchTypePeriodStat</FIELDS>
                        <REPEAT>TC_VchTypePeriodStat</REPEAT>
                    </LINE>
                    <FIELD NAME= "TC_VchTypeName" ISMODIFY= "No" ISFIXED= "No" ISINITIALIZE= "No"  ISOPTION= "No" ISINTERNAL= "No">
                        <SET>$Name</SET>
                        <XMLTAG>Name</XMLTAG>
                    </FIELD>
                    <FIELD NAME= "TC_VchTypeTotalCount" ISMODIFY= "No" ISFIXED= "No" ISINITIALIZE= "No"  ISOPTION= "No" ISINTERNAL= "No">
                        <SET>($$DirectTotalVch:$Name)+($$DirectOptionalVch:$Name)+($$DirectCancVch:$Name)</SET>
                        <XMLTAG>TotalCount</XMLTAG>
                    </FIELD>
                    <FIELD NAME= "TC_VchTypePeriodStat" ISMODIFY= "No" ISFIXED= "No" ISINITIALIZE= "No"  ISOPTION= "No" ISINTERNAL= "No">
                        <XMLTAG>PeriodStat</XMLTAG>
                        <FIELDS>TC_VchTypeFromDate</FIELDS>
                        <FIELDS>TC_VchTypeToDate</FIELDS>
                        <FIELDS>TC_VchTypeCancCount</FIELDS>
                        <FIELDS>TC_VchTypeOptCount,TC_OptionalAndCancelledCount</FIELDS>
                        <FIELDS>TC_VchTypeTotalPeriodCount,TC_TotalAccountingVoucherCount,TC_TotalInvoiceVoucherCount,TC_TotalInventoryVoucherCount</FIELDS>
                    </FIELD>
                    <FIELD NAME= "TC_VchTypeFromDate" ISMODIFY= "No" ISFIXED= "No" ISINITIALIZE= "No"  ISOPTION= "No" ISINTERNAL= "No">
                        <SET>$$TC_TransformDateToXSD:##(Report,"TC_AutoColumnStats").SVFROMDATE</SET>
                        <XMLTAG>FromDate</XMLTAG>
                        <INVISIBLE>$$ISEmpty:$$value</INVISIBLE>
                    </FIELD>
                    <FIELD NAME= "TC_VchTypeToDate" ISMODIFY= "No" ISFIXED= "No" ISINITIALIZE= "No"  ISOPTION= "No" ISINTERNAL= "No">
                        <SET>$$TC_TransformDateToXSD:##SVToDate</SET>
                        <XMLTAG>ToDate</XMLTAG>
                    </FIELD>
                    <FIELD NAME= "TC_VchTypeTotalPeriodCount" ISMODIFY= "No" ISFIXED= "No"  ISINITIALIZE= "No" ISOPTION= "No" ISINTERNAL= "No">
                        <SET>$TotalPeriodCount</SET>
                        <XMLTAG>TotalCount</XMLTAG>
                    </FIELD>
                    <FIELD NAME= "TC_VchTypeOptCount" ISMODIFY= "No" ISFIXED= "No" ISINITIALIZE= "No"  ISOPTION= "No" ISINTERNAL= "No">
                        <SET>$OptionalCount</SET>
                        <XMLTAG>OtionalCount</XMLTAG>
                    </FIELD>
                    <FIELD NAME= "TC_VchTypeCancCount" ISMODIFY= "No" ISFIXED= "No" ISINITIALIZE= "No"  ISOPTION= "No" ISINTERNAL= "No">
                        <SET>$CancelledCount</SET>
                        <XMLTAG>CancelledCount</XMLTAG>
                    </FIELD>
                    <FIELD NAME= "TC_TotalAccountingVoucherCount" ISMODIFY= "No" ISFIXED= "No"  ISINITIALIZE= "No" ISOPTION= "No" ISINTERNAL= "No">
                        <SET>$TotalAccountingVoucherCount</SET>
                        <XMLTAG>TotalAccountingVoucherCount</XMLTAG>
                    </FIELD>
                    <FIELD NAME= "TC_TotalInvoiceVoucherCount" ISMODIFY= "No" ISFIXED= "No"  ISINITIALIZE= "No" ISOPTION= "No" ISINTERNAL= "No">
                        <SET>$TotalInvoiceVoucherCount</SET>
                        <XMLTAG>TotalInvoiceVoucherCount</XMLTAG>
                    </FIELD>
                    <FIELD NAME= "TC_TotalInventoryVoucherCount" ISMODIFY= "No" ISFIXED= "No"  ISINITIALIZE= "No" ISOPTION= "No" ISINTERNAL= "No">
                        <SET>$TotalInventoryVoucherCount</SET>
                        <XMLTAG>TotalInventoryVoucherCount</XMLTAG>
                    </FIELD>
                    <FIELD NAME= "TC_OptionalAndCancelledCount" ISMODIFY= "No" ISFIXED= "No"  ISINITIALIZE= "No" ISOPTION= "No" ISINTERNAL= "No">
                        <SET>$dsfDate</SET>
                        <XMLTAG>OptionalAndCancelledCount</XMLTAG>
                    </FIELD>
                    <OBJECT NAME= "VoucherType" ISMODIFY= "Yes">
                        <LOCALFORMULA>CancelledCount:$CancVal</LOCALFORMULA>
                        <LOCALFORMULA>OptionalCount:$$DirectOptionalVch:$Name</LOCALFORMULA>
                    </OBJECT>
                    <COLLECTION NAME= "TC_VchTypeCollection" ISMODIFY= "No" ISFIXED= "No"  ISINITIALIZE= "No" ISOPTION= "No" ISINTERNAL= "No">
                        <TYPE>VoucherTypes</TYPE>
                        <BELONGSTO>None</BELONGSTO>
                        <FETCH>Name,CancelledCount,OptionalCount</FETCH>
                        <COMPUTE>dsfDate :##SVFROMDATE</COMPUTE>
                        <COMPUTE>TotalPeriodCount : ($$DirectTotalVch:$Name) + $OptionalCount + $CancelledCount</COMPUTE>
                        <COMPUTE>OptionalAndCancelledCount :$$AsReqObj:$$FilterCount:Vouchers:OptionalAndCancelledFilter</COMPUTE>
                        <COMPUTE>TotalAccountingVoucherCount:$$AsReqObj:$$FilterCount:Vouchers:AccountingVoucherFilter</COMPUTE>
                        <COMPUTE>TotalInvoiceVoucherCount:$$AsReqObj:$$CollectionField:$test:1:Vouchers</COMPUTE>
                        <COMPUTE>TotalInventoryVoucherCount:$$AsReqObj:$$FilterCount:Vouchers:InventoryVoucherFilter</COMPUTE>
                        <LOCAL>Collection:TC_VchTypeCollectionCustom:ParamVar:SVFROMDATE:Date:##SVFROMDATE</LOCAL>
                        <LOCAL>Collection:TC_VchTypeCollectionCustom:ParamVar:SVToDATE:Date:##SVToDATE</LOCAL>
                    </COLLECTION>
                    <COLLECTION NAME= "TC_VchTypeCollectionCustom" ISMODIFY= "No" ISFIXED= "No"  ISINITIALIZE= "No" ISOPTION= "No" ISINTERNAL= "No">
                        <TYPE>Vouchers:VoucherType</TYPE>
                        <CHILDOF>$Name</CHILDOF>
                    </COLLECTION>
                    <COLLECTION NAME= "TC_VchTypePeriodCollection" ISMODIFY= "No" ISFIXED= "No"  ISINITIALIZE= "No" ISOPTION= "No" ISINTERNAL= "No">
                        <COLLECTION>TC_VchTypeCollection:PeriodCollection</COLLECTION>
                    </COLLECTION>
                    <SYSTEM TYPE= "Formulae" NAME= "OptionalAndCancelledFilter">$IsOptional AND $IsCancelled</SYSTEM>
                    <SYSTEM TYPE= "Formulae" NAME= "AccountingVoucherFilter">$PERSISTEDVIEW = $$SysName:AcctgVchView AND NOT $$IsAttendance:$VOUCHERTYPENAME</SYSTEM>
                    <SYSTEM TYPE= "Formulae" NAME= "InvoiceVoucherFilter">$PERSISTEDVIEW = $$SysName:InvVchView</SYSTEM>
                    <SYSTEM TYPE= "Formulae" NAME= "InventoryVoucherFilter">$PERSISTEDVIEW = $$SysName:ConsVchView or @@MfgJournalVoucherFilter</SYSTEM>
                    <SYSTEM TYPE= "Formulae" NAME= "MfgJournalVoucherFilter">$PERSISTEDVIEW = $$SysName:MulConsVchView</SYSTEM>
                    <SYSTEM TYPE= "Formulae" NAME= "AttndVoucherFilter">$PERSISTEDVIEW = $$SysName:AcctgVchView AND $$IsAttendance:$VOUCHERTYPENAME</SYSTEM>
                    <SYSTEM TYPE= "Formulae" NAME= "PayslipVoucherFilter">$PERSISTEDVIEW = $$SysName:PaySlipVchView</SYSTEM>
                    <FUNCTION NAME= "TC_GetBooleanFromLogicField" ISMODIFY= "No" ISFIXED= "No"  ISINITIALIZE= "No" ISOPTION= "No" ISINTERNAL= "No">
                        <Parameter>val : Logical : None</Parameter>
                        <Returns>String</Returns>
                        <Action>000 : If : $$ISEmpty:##val</Action>
                        <Action>001 :Return : ##val</Action>
                        <Action>002 : Else :</Action>
                        <Action>003 : If : ##val </Action>
                        <Action>004 :Return :"true"</Action>
                        <Action>005 : Else :</Action>
                        <Action>006 :Return : "false"</Action>
                        <Action>007 : End If</Action>
                        <Action>008 : End If</Action>
                    </FUNCTION>
                    <FUNCTION NAME= "TC_TransformDateToXSD" ISMODIFY= "No" ISFIXED= "No"  ISINITIALIZE= "No" ISOPTION= "No" ISINTERNAL= "No">
                        <Parameter>ParamInputDate : Date</Parameter>
                        <VARIABLES>ParamSeparator : String : "-"</VARIABLES>
                        <VARIABLES>TempVarYear : String</VARIABLES>
                        <VARIABLES>TempVarMonth : String</VARIABLES>
                        <VARIABLES>TempVarDate : String</VARIABLES>
                        <Returns>String</Returns>
                        <Action>01 : If : NOT $$IsEmpty:##ParamInputDate</Action>
                        <Action>02 : Set : TempVarYear : $$Zerofill:($$YearofDate:##ParamInputDate):4</Action>
                        <Action>03 : Set : TempVarMonth : $$Zerofill:($$MonthofDate:##ParamInputDate):2</Action>
                        <Action>04 : Set : TempVarDate : $$Zerofill:($$DayofDate:##ParamInputDate):2</Action>
                        <Action>05 : Return : $$String:##TempVarYear + $$String:##ParamSeparator + $$String:##TempVarMonth + $$String:##ParamSeparator + $$String:##TempVarDate</Action>
                        <Action>06 : End If</Action>
                        <Action>07 : Return : ""</Action>
                    </FUNCTION>
                </TDLMESSAGE>
            </TDL>
        </DESC>
        <DATA />
    </BODY>
</ENVELOPE>
```

#### 4.2.4 `Ledgers`
```xml
<ENVELOPE Action="">
  <HEADER>
    <VERSION>1</VERSION>
    <TALLYREQUEST>EXPORT</TALLYREQUEST>
    <TYPE>COLLECTION</TYPE>
    <ID>CUSTOMLEDGERCOL</ID>
  </HEADER>
  <BODY>
    <DESC>
      <STATICVARIABLES />
      <TDL>
        <TDLMESSAGE>
          <COLLECTION ISMODIFY="No" ISFIXED="No" ISINITIALIZE="No" ISOPTION="No" ISINTERNAL="No" NAME="CUSTOMLEDGERCOL">
            <TYPE>LEDGER</TYPE>
          </COLLECTION>
        </TDLMESSAGE>
      </TDL>
    </DESC>
  </BODY>
</ENVELOPE>
```

#### 4.2.5 `CostCategories`
```xml
<ENVELOPE Action="">
  <HEADER>
    <VERSION>1</VERSION>
    <TALLYREQUEST>EXPORT</TALLYREQUEST>
    <TYPE>COLLECTION</TYPE>
    <ID>CUSTOMCOSTCATEGORYCOL</ID>
  </HEADER>
  <BODY>
    <DESC>
      <STATICVARIABLES />
      <TDL>
        <TDLMESSAGE>
          <COLLECTION ISMODIFY="No" ISFIXED="No" ISINITIALIZE="No" ISOPTION="No" ISINTERNAL="No" NAME="CUSTOMCOSTCATEGORYCOL">
            <TYPE>COSTCATEGORY</TYPE>
          </COLLECTION>
        </TDLMESSAGE>
      </TDL>
    </DESC>
  </BODY>
</ENVELOPE>
```

#### 4.2.6 `CostCentres`, `EmployeeGroups`, and `Employees`
In the Postman collection, `CostCentres` uses:
```xml
<ENVELOPE Action="">
  <HEADER>
    <VERSION>1</VERSION>
    <TALLYREQUEST>EXPORT</TALLYREQUEST>
    <TYPE>COLLECTION</TYPE>
    <ID>CUSTOMCOSTCENTRECOL</ID>
  </HEADER>
  <BODY>
    <DESC>
      <STATICVARIABLES />
      <TDL>
        <TDLMESSAGE>
          <COLLECTION ISMODIFY="No" ISFIXED="No" ISINITIALIZE="No" ISOPTION="No" ISINTERNAL="No" NAME="CUSTOMCOSTCENTRECOL">
            <TYPE>COSTCENTRE</TYPE>
            <FILTERS>IsEmployeeGroup</FILTERS>
            <FILTERS>IsPayroll</FILTERS>
          </COLLECTION>
          <SYSTEM TYPE="Formulae" NAME="IsEmployeeGroup">Not $ISEMPLOYEEGROUP</SYSTEM>
          <SYSTEM TYPE="Formulae" NAME="IsPayroll">Not $FORPAYROLL</SYSTEM>
        </TDLMESSAGE>
      </TDL>
    </DESC>
  </BODY>
</ENVELOPE>
```
And for `EmployeeGroups` and `Employees` (per TallyConnector's `COSTCENTRE` discriminator):
- **EmployeeGroups:**
  ```xml
  <SYSTEM TYPE="Formulae" NAME="IsEmployeeGroup">$ISEMPLOYEEGROUP</SYSTEM>
  ```
- **Employees:**
  ```xml
  <SYSTEM TYPE="Formulae" NAME="IsEmployeeGroup">Not $ISEMPLOYEEGROUP</SYSTEM>
  <SYSTEM TYPE="Formulae" NAME="IsPayroll">$FORPAYROLL</SYSTEM>
  ```

#### 4.2.7 `StockCategories`
```xml
<ENVELOPE Action="">
  <HEADER>
    <VERSION>1</VERSION>
    <TALLYREQUEST>EXPORT</TALLYREQUEST>
    <TYPE>COLLECTION</TYPE>
    <ID>CUSTOMSTOCKCATEGORYCOL</ID>
  </HEADER>
  <BODY>
    <DESC>
      <STATICVARIABLES />
      <TDL>
        <TDLMESSAGE>
          <COLLECTION ISMODIFY="No" ISFIXED="No" ISINITIALIZE="No" ISOPTION="No" ISINTERNAL="No" NAME="CUSTOMSTOCKCATEGORYCOL">
            <TYPE>STOCKCATEGORY</TYPE>
          </COLLECTION>
        </TDLMESSAGE>
      </TDL>
    </DESC>
  </BODY>
</ENVELOPE>
```

#### 4.2.8 `StockGroups`
```xml
<ENVELOPE Action="">
  <HEADER>
    <VERSION>1</VERSION>
    <TALLYREQUEST>EXPORT</TALLYREQUEST>
    <TYPE>COLLECTION</TYPE>
    <ID>CUSTOMSTOCKGROUPCOL</ID>
  </HEADER>
  <BODY>
    <DESC>
      <STATICVARIABLES />
      <TDL>
        <TDLMESSAGE>
          <COLLECTION ISMODIFY="No" ISFIXED="No" ISINITIALIZE="No" ISOPTION="No" ISINTERNAL="No" NAME="CUSTOMSTOCKGROUPCOL">
            <TYPE>STOCKGROUP</TYPE>
          </COLLECTION>
        </TDLMESSAGE>
      </TDL>
    </DESC>
  </BODY>
</ENVELOPE>
```

#### 4.2.9 `StockItems`
```xml
<ENVELOPE Action="">
  <HEADER>
    <VERSION>1</VERSION>
    <TALLYREQUEST>EXPORT</TALLYREQUEST>
    <TYPE>COLLECTION</TYPE>
    <ID>CUSTOMSTOCKITEMCOL</ID>
  </HEADER>
  <BODY>
    <DESC>
      <STATICVARIABLES />
      <TDL>
        <TDLMESSAGE>
          <COLLECTION ISMODIFY="No" ISFIXED="No" ISINITIALIZE="No" ISOPTION="No" ISINTERNAL="No" NAME="CUSTOMSTOCKITEMCOL">
            <TYPE>STOCKITEM</TYPE>
          </COLLECTION>
        </TDLMESSAGE>
      </TDL>
    </DESC>
  </BODY>
</ENVELOPE>
```

#### 4.2.10 `Units`
```xml
<ENVELOPE Action="">
  <HEADER>
    <VERSION>1</VERSION>
    <TALLYREQUEST>EXPORT</TALLYREQUEST>
    <TYPE>COLLECTION</TYPE>
    <ID>CUSTOMUNITCOL</ID>
  </HEADER>
  <BODY>
    <DESC>
      <STATICVARIABLES />
      <TDL>
        <TDLMESSAGE>
          <COLLECTION ISMODIFY="No" ISFIXED="No" ISINITIALIZE="No" ISOPTION="No" ISINTERNAL="No" NAME="CUSTOMUNITCOL">
            <TYPE>UNIT</TYPE>
          </COLLECTION>
        </TDLMESSAGE>
      </TDL>
    </DESC>
  </BODY>
</ENVELOPE>
```

#### 4.2.11 `Godowns`
```xml
<ENVELOPE Action="">
  <HEADER>
    <VERSION>1</VERSION>
    <TALLYREQUEST>EXPORT</TALLYREQUEST>
    <TYPE>COLLECTION</TYPE>
    <ID>CUSTOMGODOWNCOL</ID>
  </HEADER>
  <BODY>
    <DESC>
      <STATICVARIABLES />
      <TDL>
        <TDLMESSAGE>
          <COLLECTION ISMODIFY="No" ISFIXED="No" ISINITIALIZE="No" ISOPTION="No" ISINTERNAL="No" NAME="CUSTOMGODOWNCOL">
            <TYPE>GODOWN</TYPE>
          </COLLECTION>
        </TDLMESSAGE>
      </TDL>
    </DESC>
  </BODY>
</ENVELOPE>
```

#### 4.2.12 `VoucherTypes`
```xml
<ENVELOPE Action="">
  <HEADER>
    <VERSION>1</VERSION>
    <TALLYREQUEST>EXPORT</TALLYREQUEST>
    <TYPE>COLLECTION</TYPE>
    <ID>CUSTOMVOUCHERTYPECOL</ID>
  </HEADER>
  <BODY>
    <DESC>
      <STATICVARIABLES />
      <TDL>
        <TDLMESSAGE>
          <COLLECTION ISMODIFY="No" ISFIXED="No" ISINITIALIZE="No" ISOPTION="No" ISINTERNAL="No" NAME="CUSTOMVOUCHERTYPECOL">
            <TYPE>VOUCHERTYPE</TYPE>
          </COLLECTION>
        </TDLMESSAGE>
      </TDL>
    </DESC>
  </BODY>
</ENVELOPE>
```

---

### 4.3 `Export / Collections / Voucher`

```xml
<ENVELOPE Action="">
  <HEADER>
    <VERSION>1</VERSION>
    <TALLYREQUEST>EXPORT</TALLYREQUEST>
    <TYPE>COLLECTION</TYPE>
    <ID>CUSTOMVOUCHERCOL</ID>
  </HEADER>
  <BODY>
    <DESC>
      <STATICVARIABLES />
      <TDL>
        <TDLMESSAGE>
          <COLLECTION ISMODIFY="No" ISFIXED="No" ISINITIALIZE="No" ISOPTION="No" ISINTERNAL="No" NAME="CUSTOMVOUCHERCOL">
            <TYPE>VOUCHER</TYPE>
          </COLLECTION>
        </TDLMESSAGE>
      </TDL>
    </DESC>
  </BODY>
</ENVELOPE>
```

---

### 4.4 `Export / Reports`

#### 4.4.1 `Stats_Master` (`MasterTypeStat`)
```xml
<ENVELOPE Action="">
  <HEADER>
    <VERSION>1</VERSION>
    <TALLYREQUEST>EXPORT</TALLYREQUEST>
    <TYPE>DATA</TYPE>
    <ID>MasterTypeStat</ID>
  </HEADER>
  <BODY>
    <DESC>
      <STATICVARIABLES>
        <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
        <SVCURRENTCOMPANY>ABC Company Ltd</SVCURRENTCOMPANY>
      </STATICVARIABLES>
      <TDL>
        <TDLMESSAGE>
          <REPORT ISMODIFY="No" ISFIXED="No" ISINITIALIZE="No" ISOPTION="No" ISINTERNAL="No" NAME="MasterTypeStat">
            <FORMS>MasterTypeStat</FORMS>
          </REPORT>
          <FORM ISMODIFY="No" ISFIXED="No" ISINITIALIZE="No" ISOPTION="No" ISINTERNAL="No" NAME="MasterTypeStat">
            <TOPPARTS>MasterTypeStat</TOPPARTS>
            <XMLTAG>MasterTypeStat.LIST</XMLTAG>
          </FORM>
          <PART ISMODIFY="No" ISFIXED="No" ISINITIALIZE="No" ISOPTION="No" ISINTERNAL="No" NAME="MasterTypeStat">
            <TOPLINES>MasterTypeStat</TOPLINES>
            <REPEAT>MasterTypeStat : STATObjects</REPEAT>
            <SCROLLED>Vertical</SCROLLED>
          </PART>
          <LINE ISMODIFY="No" ISFIXED="No" ISINITIALIZE="No" ISOPTION="No" ISINTERNAL="No" NAME="MasterTypeStat">
            <FIELDS>NAME</FIELDS>
            <FIELDS>COUNT</FIELDS>
            <XMLTAG>MasterTypeStat</XMLTAG>
          </LINE>
          <FIELD ISMODIFY="No" ISFIXED="No" ISINITIALIZE="No" ISOPTION="No" ISINTERNAL="No" NAME="NAME">
            <SET>$NAME</SET>
            <XMLTAG>NAME</XMLTAG>
          </FIELD>
          <FIELD ISMODIFY="No" ISFIXED="No" ISINITIALIZE="No" ISOPTION="No" ISINTERNAL="No" NAME="COUNT">
            <SET>$StatVal</SET>
            <XMLTAG>COUNT</XMLTAG>
          </FIELD>
        </TDLMESSAGE>
      </TDL>
    </DESC>
  </BODY>
</ENVELOPE>
```

#### 4.4.2 `Stats_Voucher` (`VoucherTypeStat`)
```xml
<ENVELOPE Action="">
  <HEADER>
    <VERSION>1</VERSION>
    <TALLYREQUEST>EXPORT</TALLYREQUEST>
    <TYPE>DATA</TYPE>
    <ID>VoucherTypeStat</ID>
  </HEADER>
  <BODY>
    <DESC>
      <STATICVARIABLES>
        <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
        <SVCURRENTCOMPANY>ABC Company Ltd</SVCURRENTCOMPANY>
        <SVFROMDATE TYPE="Date">01-04-2022</SVFROMDATE>
        <SVTODATE TYPE="Date">31-03-2023</SVTODATE>
      </STATICVARIABLES>
      <TDL>
        <TDLMESSAGE>
          <REPORT ISMODIFY="No" ISFIXED="No" ISINITIALIZE="No" ISOPTION="No" ISINTERNAL="No" NAME="VoucherTypeStat">
            <FORMS>VoucherTypeStat</FORMS>
          </REPORT>
          <FORM ISMODIFY="No" ISFIXED="No" ISINITIALIZE="No" ISOPTION="No" ISINTERNAL="No" NAME="VoucherTypeStat">
            <TOPPARTS>VoucherTypeStat</TOPPARTS>
            <XMLTAG>VoucherTypeStat.LIST</XMLTAG>
          </FORM>
          <PART ISMODIFY="No" ISFIXED="No" ISINITIALIZE="No" ISOPTION="No" ISINTERNAL="No" NAME="VoucherTypeStat">
            <TOPLINES>VoucherTypeStat</TOPLINES>
            <REPEAT>VoucherTypeStat : STATVchType</REPEAT>
            <SCROLLED>Vertical</SCROLLED>
          </PART>
          <LINE ISMODIFY="No" ISFIXED="No" ISINITIALIZE="No" ISOPTION="No" ISINTERNAL="No" NAME="VoucherTypeStat">
            <FIELDS>CANCELLEDCOUNT</FIELDS>
            <FIELDS>NAME</FIELDS>
            <FIELDS>COUNT</FIELDS>
            <XMLTAG>VoucherTypeStat</XMLTAG>
          </LINE>
          <FIELD ISMODIFY="No" ISFIXED="No" ISINITIALIZE="No" ISOPTION="No" ISINTERNAL="No" NAME="CANCELLEDCOUNT">
            <SET>$CancVal</SET>
            <XMLTAG>CANCELLEDCOUNT</XMLTAG>
          </FIELD>
          <FIELD ISMODIFY="No" ISFIXED="No" ISINITIALIZE="No" ISOPTION="No" ISINTERNAL="No" NAME="NAME">
            <SET>$NAME</SET>
            <XMLTAG>NAME</XMLTAG>
          </FIELD>
          <FIELD ISMODIFY="No" ISFIXED="No" ISINITIALIZE="No" ISOPTION="No" ISINTERNAL="No" NAME="COUNT">
            <SET>$StatVal</SET>
            <XMLTAG>COUNT</XMLTAG>
          </FIELD>
        </TDLMESSAGE>
      </TDL>
    </DESC>
  </BODY>
</ENVELOPE>
```

#### 4.4.3 `LicenseInfo`
```xml
<ENVELOPE Action="">
  <HEADER>
    <VERSION>1</VERSION>
    <TALLYREQUEST>EXPORT</TALLYREQUEST>
    <TYPE>DATA</TYPE>
    <ID>LicenseInfo</ID>
  </HEADER>
  <BODY>
    <DESC>
      <STATICVARIABLES>
        <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
      </STATICVARIABLES>
      <TDL>
        <TDLMESSAGE>
          <REPORT ISMODIFY="No" ISFIXED="No" ISINITIALIZE="No" ISOPTION="No" ISINTERNAL="No" NAME="LicenseInfo">
            <FORMS>LicenseInfo</FORMS>
          </REPORT>
          <FORM ISMODIFY="No" ISFIXED="No" ISINITIALIZE="No" ISOPTION="No" ISINTERNAL="No" NAME="LicenseInfo">
            <TOPPARTS>LicenseInfo</TOPPARTS>
            <XMLTAG>LicenseInfo</XMLTAG>
          </FORM>
          <PART ISMODIFY="No" ISFIXED="No" ISINITIALIZE="No" ISOPTION="No" ISINTERNAL="No" NAME="LicenseInfo">
            <TOPLINES>LicenseInfo</TOPLINES>
            <SCROLLED>Vertical</SCROLLED>
          </PART>
          <LINE ISMODIFY="No" ISFIXED="No" ISINITIALIZE="No" ISOPTION="No" ISINTERNAL="No" NAME="LicenseInfo">
            <FIELDS>SERIALNUMBER</FIELDS>
            <FIELDS>REMOTESERIALNUMBER</FIELDS>
            <FIELDS>ACCOUNTID</FIELDS>
            <FIELDS>ADMINMAILID</FIELDS>
            <FIELDS>ISADMIN</FIELDS>
            <FIELDS>ISEDUCATIONALMODE</FIELDS>
            <FIELDS>ISSILVER</FIELDS>
            <FIELDS>ISGOLD</FIELDS>
            <FIELDS>PLANNAME</FIELDS>
            <FIELDS>ISINDIAN</FIELDS>
            <FIELDS>ISREMOTEACCESSMODE</FIELDS>
            <FIELDS>ISLICCLIENTMODE</FIELDS>
            <FIELDS>APPLICATIONPATH</FIELDS>
            <FIELDS>DATAPATH</FIELDS>
            <FIELDS>USERLEVEL</FIELDS>
            <FIELDS>USERNAME</FIELDS>
            <FIELDS>TALLYVERSION</FIELDS>
          </LINE>
          <FIELD ISMODIFY="No" ISFIXED="No" ISINITIALIZE="No" ISOPTION="No" ISINTERNAL="No" NAME="SERIALNUMBER">
            <SET>$$LicenseInfo:SerialNumber</SET>
            <XMLTAG>SERIALNUMBER</XMLTAG>
          </FIELD>
          <FIELD ISMODIFY="No" ISFIXED="No" ISINITIALIZE="No" ISOPTION="No" ISINTERNAL="No" NAME="REMOTESERIALNUMBER">
            <SET>$$LicenseInfo:RemoteSerialNumber</SET>
            <XMLTAG>REMOTESERIALNUMBER</XMLTAG>
          </FIELD>
          <FIELD ISMODIFY="No" ISFIXED="No" ISINITIALIZE="No" ISOPTION="No" ISINTERNAL="No" NAME="ACCOUNTID">
            <SET>$$LicenseInfo:AccountID</SET>
            <XMLTAG>ACCOUNTID</XMLTAG>
          </FIELD>
          <FIELD ISMODIFY="No" ISFIXED="No" ISINITIALIZE="No" ISOPTION="No" ISINTERNAL="No" NAME="ADMINMAILID">
            <SET>$$LicenseInfo:AdminEmailID</SET>
            <XMLTAG>ADMINMAILID</XMLTAG>
          </FIELD>
          <FIELD ISMODIFY="No" ISFIXED="No" ISINITIALIZE="No" ISOPTION="No" ISINTERNAL="No" NAME="ISADMIN">
            <SET>$$LicenseInfo:IsAdmin</SET>
            <XMLTAG>ISADMIN</XMLTAG>
          </FIELD>
          <FIELD ISMODIFY="No" ISFIXED="No" ISINITIALIZE="No" ISOPTION="No" ISINTERNAL="No" NAME="ISEDUCATIONALMODE">
            <SET>$$LicenseInfo:IsEducationalMode</SET>
            <XMLTAG>ISEDUCATIONALMODE</XMLTAG>
          </FIELD>
          <FIELD ISMODIFY="No" ISFIXED="No" ISINITIALIZE="No" ISOPTION="No" ISINTERNAL="No" NAME="ISSILVER">
            <SET>$$LicenseInfo:IsAdmin</SET>
            <XMLTAG>ISSILVER</XMLTAG>
          </FIELD>
          <FIELD ISMODIFY="No" ISFIXED="No" ISINITIALIZE="No" ISOPTION="No" ISINTERNAL="No" NAME="ISGOLD">
            <SET>$$LicenseInfo:IsAdmin</SET>
            <XMLTAG>ISGOLD</XMLTAG>
          </FIELD>
          <FIELD ISMODIFY="No" ISFIXED="No" ISINITIALIZE="No" ISOPTION="No" ISINTERNAL="No" NAME="PLANNAME">
            <SET>If $$LicenseInfo:IsEducationalMode Then "Educational Version" ELSE  If $$LicenseInfo:IsSilver Then "Silver" ELSE  If $$LicenseInfo:IsGold Then "Gold" else ""</SET>
            <XMLTAG>PLANNAME</XMLTAG>
          </FIELD>
          <FIELD ISMODIFY="No" ISFIXED="No" ISINITIALIZE="No" ISOPTION="No" ISINTERNAL="No" NAME="ISINDIAN">
            <SET>$$LicenseInfo:IsAdmin</SET>
            <XMLTAG>ISINDIAN</XMLTAG>
          </FIELD>
          <FIELD ISMODIFY="No" ISFIXED="No" ISINITIALIZE="No" ISOPTION="No" ISINTERNAL="No" NAME="ISREMOTEACCESSMODE">
            <SET>$$LicenseInfo:IsRemoteAccessMode</SET>
            <XMLTAG>ISREMOTEACCESSMODE</XMLTAG>
          </FIELD>
          <FIELD ISMODIFY="No" ISFIXED="No" ISINITIALIZE="No" ISOPTION="No" ISINTERNAL="No" NAME="ISLICCLIENTMODE">
            <SET>$$LicenseInfo:IsLicClientMode</SET>
            <XMLTAG>ISLICCLIENTMODE</XMLTAG>
          </FIELD>
          <FIELD ISMODIFY="No" ISFIXED="No" ISINITIALIZE="No" ISOPTION="No" ISINTERNAL="No" NAME="APPLICATIONPATH">
            <SET>$$SysInfo:ApplicationPath</SET>
            <XMLTAG>APPLICATIONPATH</XMLTAG>
          </FIELD>
          <FIELD ISMODIFY="No" ISFIXED="No" ISINITIALIZE="No" ISOPTION="No" ISINTERNAL="No" NAME="DATAPATH">
            <SET>##SVCurrentPath</SET>
            <XMLTAG>DATAPATH</XMLTAG>
          </FIELD>
          <FIELD ISMODIFY="No" ISFIXED="No" ISINITIALIZE="No" ISOPTION="No" ISINTERNAL="No" NAME="USERLEVEL">
            <SET>$$cmpuserlevel</SET>
            <XMLTAG>USERLEVEL</XMLTAG>
          </FIELD>
          <FIELD ISMODIFY="No" ISFIXED="No" ISINITIALIZE="No" ISOPTION="No" ISINTERNAL="No" NAME="USERNAME">
            <SET>$$cmpusername</SET>
            <XMLTAG>USERNAME</XMLTAG>
          </FIELD>
          <FIELD ISMODIFY="No" ISFIXED="No" ISINITIALIZE="No" ISOPTION="No" ISINTERNAL="No" NAME="TALLYVERSION">
            <SET>if @@CapProductDetails contains "Tally.ERP 9" then $$SPrintf:@@CapProductDetails:@@VersionGetProductSeries:@@VersionReleaseString:@@VersionBuildString:@@ProductBitnessStr:($$String:@@MajorReleaseeFormula):($$String:@@MinorReleaseFormula):"0":@@CapBuildNumberFormula else $$SPrintf:@@CapProductDetails:@@VersionReleaseString:@@VersionBuildString:@@ProductBitnessStr:($$String:@@MajorReleaseeFormula):($$String:@@MinorReleaseFormula):"0":@@CapBuildNumberFormula</SET>
            <XMLTAG>TALLYVERSION</XMLTAG>
          </FIELD>
        </TDLMESSAGE>
      </TDL>
    </DESC>
  </BODY>
</ENVELOPE>
```

---

### 4.5 `GetActiveCompany`

```xml
<ENVELOPE Action="">
  <HEADER>
    <VERSION>1</VERSION>
    <TALLYREQUEST>EXPORT</TALLYREQUEST>
    <TYPE>COLLECTION</TYPE>
    <ID>CUSTOMCOMPANYCOL</ID>
  </HEADER>
  <BODY>
    <DESC>
      <STATICVARIABLES />
      <TDL>
        <TDLMESSAGE>
          <COLLECTION ISMODIFY="No" ISFIXED="No" ISINITIALIZE="Yes" ISOPTION="No" ISINTERNAL="No" NAME="CUSTOMCOMPANYCOL">
            <TYPE>COMPANY</TYPE>
            <NATIVEMETHOD>NAME</NATIVEMETHOD>
            <NATIVEMETHOD>GUID</NATIVEMETHOD>
            <NATIVEMETHOD>BOOKSFROM</NATIVEMETHOD>
            <NATIVEMETHOD>STARTINGFROM</NATIVEMETHOD>
            <NATIVEMETHOD>COMPANYNUMBER</NATIVEMETHOD>
            <NATIVEMETHOD>ENDINGAT</NATIVEMETHOD>
            <FILTERS>ActiveCompFilt</FILTERS>
          </COLLECTION>
          <SYSTEM TYPE="Formulae" NAME="ActiveCompFilt">$Name = ##SVCURRENTCOMPANY</SYSTEM>
        </TDLMESSAGE>
      </TDL>
    </DESC>
  </BODY>
</ENVELOPE>
```

---

### 4.6 `Import` Payloads (For Reference)

#### 4.6.1 `Import / Masters / Ledger / BasicLedger`
```xml
<ENVELOPE Action="">
  <HEADER>
    <VERSION>1</VERSION>
    <TALLYREQUEST>IMPORT</TALLYREQUEST>
    <TYPE>DATA</TYPE>
    <ID>All Masters</ID>
  </HEADER>
  <BODY>
    <DESC>
      <STATICVARIABLES />
    </DESC>
    <DATA>
      <TALLYMESSAGE>
        <LEDGER Action="">
          <MASTERID p6:nil="true" xmlns:p6="http://www.w3.org/2001/XMLSchema-instance" />
          <ALTERID p6:nil="true" xmlns:p6="http://www.w3.org/2001/XMLSchema-instance" />
          <NAME>Test Ledger</NAME>
          <PARENT>Sundry Debtors</PARENT>
          <TAXTYPE>Others</TAXTYPE>
          <GSTDUTYHEAD p6:nil="true" xmlns:p6="http://www.w3.org/2001/XMLSchema-instance" />
          <RATEOFTAXCALCULATION p6:nil="true" xmlns:p6="http://www.w3.org/2001/XMLSchema-instance" />
          <GSTREGISTRATIONTYPE />
          <GSTNATUREOFSUPPLY p6:nil="true" xmlns:p6="http://www.w3.org/2001/XMLSchema-instance" />
          <ADDRESS.LIST />
          <LANGUAGENAME.LIST>
            <NAME.LIST>
              <NAME>Test Ledger</NAME>
            </NAME.LIST>
          </LANGUAGENAME.LIST>
        </LEDGER>
      </TALLYMESSAGE>
    </DATA>
  </BODY>
</ENVELOPE>
```

#### 4.6.2 `Import / Masters / Ledger / LedgerwithOpeningBalance`
```xml
<ENVELOPE Action="">
  <HEADER>
    <VERSION>1</VERSION>
    <TALLYREQUEST>IMPORT</TALLYREQUEST>
    <TYPE>DATA</TYPE>
    <ID>All Masters</ID>
  </HEADER>
  <BODY>
    <DESC>
      <STATICVARIABLES />
    </DESC>
    <DATA>
      <TALLYMESSAGE>
        <LEDGER Action="">
          <MASTERID p6:nil="true" xmlns:p6="http://www.w3.org/2001/XMLSchema-instance" />
          <ALTERID p6:nil="true" xmlns:p6="http://www.w3.org/2001/XMLSchema-instance" />
          <NAME>Test Ledger 2</NAME>
          <PARENT>Sundry Debtors</PARENT>
          <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>
          <OPENINGBALANCE>8000</OPENINGBALANCE>
          <TAXTYPE>Others</TAXTYPE>
          <GSTDUTYHEAD p6:nil="true" xmlns:p6="http://www.w3.org/2001/XMLSchema-instance" />
          <RATEOFTAXCALCULATION p6:nil="true" xmlns:p6="http://www.w3.org/2001/XMLSchema-instance" />
          <GSTREGISTRATIONTYPE />
          <GSTNATUREOFSUPPLY p6:nil="true" xmlns:p6="http://www.w3.org/2001/XMLSchema-instance" />
          <ADDRESS.LIST />
          <LANGUAGENAME.LIST>
            <NAME.LIST>
              <NAME>Test Ledger 2</NAME>
            </NAME.LIST>
          </LANGUAGENAME.LIST>
        </LEDGER>
      </TALLYMESSAGE>
    </DATA>
  </BODY>
</ENVELOPE>
```

#### 4.6.3 `Import / Voucher / basicVoucher`
```xml
<ENVELOPE Action="">
  <HEADER>
    <VERSION>1</VERSION>
    <TALLYREQUEST>IMPORT</TALLYREQUEST>
    <TYPE>DATA</TYPE>
    <ID>All Masters</ID>
  </HEADER>
  <BODY>
    <DESC>
      <STATICVARIABLES />
    </DESC>
    <DATA>
      <TALLYMESSAGE>
        <VOUCHER Action="Create" DATE="20221116" VCHTYPE="Sales" MASTERID="">
          <MASTERID p6:nil="true" xmlns:p6="http://www.w3.org/2001/XMLSchema-instance" />
          <ALTERID p6:nil="true" xmlns:p6="http://www.w3.org/2001/XMLSchema-instance" />
          <DATE TYPE="Date">16-11-2022</DATE>
          <VOUCHERTYPENAME>Sales</VOUCHERTYPENAME>
          <PERSISTEDVIEW>Accounting Voucher View</PERSISTEDVIEW>
          <NARRATION>Being Sales made to Test Customer</NARRATION>
          <BASICSHIPDELIVERYNOTE />
          <ALLLEDGERENTRIES.LIST>
            <INDEXNUMBER>0</INDEXNUMBER>
            <LEDGERNAME>Test Customer</LEDGERNAME>
            <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>
            <AMOUNT>-9000</AMOUNT>
          </ALLLEDGERENTRIES.LIST>
          <ALLLEDGERENTRIES.LIST>
            <INDEXNUMBER>0</INDEXNUMBER>
            <LEDGERNAME>Sales</LEDGERNAME>
            <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>
            <AMOUNT>9000</AMOUNT>
          </ALLLEDGERENTRIES.LIST>
        </VOUCHER>
      </TALLYMESSAGE>
    </DATA>
  </BODY>
</ENVELOPE>
```

#### 4.6.4 `Import / Voucher / basicInvoiceVoucher`
```xml
<ENVELOPE Action="">
  <HEADER>
    <VERSION>1</VERSION>
    <TALLYREQUEST>IMPORT</TALLYREQUEST>
    <TYPE>DATA</TYPE>
    <ID>All Masters</ID>
  </HEADER>
  <BODY>
    <DESC>
      <STATICVARIABLES />
    </DESC>
    <DATA>
      <TALLYMESSAGE>
        <VOUCHER Action="Create" DATE="20221116" VCHTYPE="Sales" MASTERID="">
          <MASTERID p6:nil="true" xmlns:p6="http://www.w3.org/2001/XMLSchema-instance" />
          <ALTERID p6:nil="true" xmlns:p6="http://www.w3.org/2001/XMLSchema-instance" />
          <DATE TYPE="Date">16-11-2022</DATE>
          <VOUCHERTYPENAME>Sales</VOUCHERTYPENAME>
          <PERSISTEDVIEW>Invoice Voucher View</PERSISTEDVIEW>
          <NARRATION>Being Sales made to Test Customer</NARRATION>
          <BASICSHIPDELIVERYNOTE />
          <PARTYNAME>Test Customer</PARTYNAME>
          <LEDGERENTRIES.LIST>
            <INDEXNUMBER>0</INDEXNUMBER>
            <LEDGERNAME>Test Customer</LEDGERNAME>
            <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>
            <AMOUNT>-9000</AMOUNT>
          </LEDGERENTRIES.LIST>
          <LEDGERENTRIES.LIST>
            <INDEXNUMBER>0</INDEXNUMBER>
            <LEDGERNAME>Sales</LEDGERNAME>
            <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>
            <AMOUNT>9000</AMOUNT>
          </LEDGERENTRIES.LIST>
        </VOUCHER>
      </TALLYMESSAGE>
    </DATA>
  </BODY>
</ENVELOPE>
```

#### 4.6.5 `Import / Voucher / VoucherwithCostCenter` & `InvoiceVoucherwithCostCenter`
Shows how Cost Centre allocations are nested inside `<ALLLEDGERENTRIES.LIST>` (or `<LEDGERENTRIES.LIST>`):
```xml
<CATEGORYALLOCATIONS.LIST>
  <CATEGORY>Primary Cost Category</CATEGORY>
  <COSTCENTREALLOCATIONS.LIST>
    <NAME>Costcent1</NAME>
    <AMOUNT>9000</AMOUNT>
  </COSTCENTREALLOCATIONS.LIST>
</CATEGORYALLOCATIONS.LIST>
```
