$(document).ready(function () {
  $('[data-toggle="tooltip"]').tooltip();
});

$(function () {
  function tcHidePageStatusAlert($pageBody) {
    if (!$pageBody || !$pageBody.length) return;
    $pageBody.find(".container-fluid.py-4 .alert").each(function () {
      var $a = $(this);
      $a.addClass("d-none");
      $a.removeClass("alert-success alert-danger");
      if (!$a.hasClass("alert-warning")) {
        $a.addClass("alert-warning");
      }
      $a.empty();
      // Also hide the wrapper so its py-4 padding doesn't create empty space
      $a.closest(".container-fluid.py-4").addClass("d-none");
    });
  }

  /** Shown in the Request URL field (Tally HTTP port). */
  var TC_DISPLAY_REQUEST_URL = "http://localhost:9000";
  /** Actual XHR target: local CORS proxy (see tally-local-proxy.js). */
  var TC_PROXY_PORT = 3000;

  /** JSON/XML choice shared across all API tabs until full page reload. */
  var tcSessionPayloadFormat = "JSON";
  /** Request URL (incl. port) shared across all API tabs until full page reload. */
  var tcSessionRequestUrl = TC_DISPLAY_REQUEST_URL;

  function tcRememberRequestUrl(urlStr) {
    var v = (urlStr != null ? String(urlStr) : "").trim();
    if (v) {
      tcSessionRequestUrl = v;
    }
  }

  function tcApplyDisplayRequestUrl($root) {
    if (!$root || !$root.length) return;
    $root.find('[data-id="requestUrl"]').each(function () {
      var $inp = $(this);
      $inp.val(tcSessionRequestUrl);
      tcSetRequestUrlFieldState($inp);
    });
  }

  /** Validate Request URL format (http://localhost|127.0.0.1:<port> only). */
  function tcValidateRequestUrl(urlStr) {
    var s = (urlStr != null ? String(urlStr) : "").trim();
    if (!s) {
      return {
        valid: false,
        message: "Enter Request URL (e.g. http://localhost:9000).",
      };
    }
    try {
      var u = new URL(s);
      if (u.protocol !== "http:") {
        return {
          valid: false,
          message: "URL must start with http:// (e.g. http://localhost:9000).",
        };
      }
      var host = u.hostname.toLowerCase();
      if (host !== "localhost" && host !== "127.0.0.1") {
        return {
          valid: false,
          message:
            "Host must be localhost or 127.0.0.1 (only the port can be changed).",
        };
      }
      if (!u.port) {
        return {
          valid: false,
          message: "URL must include a port number (e.g. http://localhost:9000).",
        };
      }
      var portNum = parseInt(u.port, 10);
      if (isNaN(portNum) || portNum < 1 || portNum > 65535) {
        return {
          valid: false,
          message: "Port must be a number between 1 and 65535.",
        };
      }
      if (
        (u.pathname && u.pathname !== "/") ||
        u.search ||
        u.hash ||
        u.username ||
        u.password
      ) {
        return {
          valid: false,
          message:
            "Only the port number can be modified (e.g. http://localhost:9000).",
        };
      }
      return { valid: true, message: "" };
    } catch (e) {
      return {
        valid: false,
        message:
          "Invalid URL format. Use http://localhost:9000 or http://127.0.0.1:9000.",
      };
    }
  }

  function tcSetRequestUrlFieldState($input, result) {
    if (!$input || !$input.length) return;
    var check = result || tcValidateRequestUrl($input.val());
    var isValid = check.valid;

    $input.toggleClass("is-invalid", !isValid);

    var $feedback = $input.siblings("[data-tc-url-feedback]");
    if (!$feedback.length) {
      $feedback = $(
        '<div class="invalid-feedback d-block" data-tc-url-feedback="1"></div>',
      );
      $input.after($feedback);
    }
    if (isValid) {
      $feedback.text("").addClass("d-none");
    } else {
      $feedback.text(check.message).removeClass("d-none");
    }
  }

  function tcNormalizePayloadFormat(val) {
    var s = (val != null ? String(val) : "JSON").trim();
    return s === "XML" ? "XML" : "JSON";
  }

  function tcSyncHotBlocks($section, fmt) {
    if (!$section || !$section.length) return;
    fmt = tcNormalizePayloadFormat(fmt);
    $section.find(".hot-block").each(function () {
      var blockFmt = $(this).attr("data-format") || "JSON";
      $(this).toggleClass("d-none", blockFmt !== fmt);
    });
  }

  /**
   * tcInjectPageHelperTexts
   * Injects three helper sub-labels below the Request URL / Validate Connection /
   * Payload Format row on every API page — managed in one place here.
   *
   *  Col 1 (Request URL)       → "Only the port number can be modified, as the request is sent to localhost"
   *  Col 2 (Validate btn)      → "Check if TallyPrime is running and a company is loaded"
   *  Col 3 (Payload Format)    → "JSON Format is supported from TallyPrime 7.0 onwards"  [JSON only]
   */
  function tcInjectPageHelperTexts($page) {
    if (!$page || !$page.length) return;

    var $pageBody = $page.find(".page-body").first();
    if (!$pageBody.length) return;

    // Find the 3-column header row by locating the requestUrl input inside it
    var $urlInput = $pageBody.find('[data-id="requestUrl"]');
    if (!$urlInput.length) return;

    // The row is the direct flex wrapper (.d-flex) that contains all three col divs
    var $row = $urlInput.closest(".d-flex.flex-wrap");
    if (!$row.length) return;

    // Use direct div children — works with both col-4 and responsive col-12.col-lg-4
    var $cols = $row.children("div");
    if ($cols.length < 3) return;

    // Remove any previously injected helper texts (safety — avoids duplicates on re-render)
    $pageBody.find(".tc-helper-text").remove();

    var helperStyle = 'class="tc-helper-text small text-muted mt-1"';

    // Col 1 — below Request URL
    $($cols[0]).append('<p ' + helperStyle + '>Only the port number can be modified, as the request is sent to localhost</p>');

    // Col 2 — below Validate Connection button (invisible label spacer is already in HTML)
    var $btnWrapper = $($cols[1]).find("div").first();
    $btnWrapper.append('<p ' + helperStyle + '>Check if TallyPrime is running and a company is loaded</p>');

    // Col 3 — below Payload Format select (shown only when JSON is selected)
    var $fmtDiv = $($cols[2]).find("div").first();
    var $jsonNote = $('<p ' + helperStyle + ' data-tc-json-note="1">JSON Format is supported from TallyPrime 7.0 onwards</p>');
    $fmtDiv.append($jsonNote);

    // Show/hide based on current format value.
    // On lg+ (3-col side-by-side): use visibility so col-3 keeps height and prevents
    // layout shift on the align-items-end row. On smaller stacked layouts d-none is fine.
    function syncJsonNote() {
      var val = $pageBody.find('[data-id="payloadFormat"]').val() || "JSON";
      var isJson = val === "JSON";
      if (window.innerWidth >= 992) {
        $jsonNote.css("visibility", isJson ? "visible" : "hidden");
      } else {
        $jsonNote.css("visibility", "visible").toggleClass("d-none", !isJson);
      }
    }
    syncJsonNote();

    // Re-sync whenever the dropdown changes
    $pageBody.find('[data-id="payloadFormat"]').off("change.tcJsonNote").on("change.tcJsonNote", syncJsonNote);
  }

  /** Port from the Request URL field (defaults to 9000). */
  function tcTallyPortFromUrl(urlStr) {
    var s = (urlStr || "").trim();
    if (!s) return "9000";
    try {
      return new URL(s).port || "9000";
    } catch (e) {
      return "9000";
    }
  }

  /** Map field URL to proxy URL (127.0.0.1:3000 + path/query/hash).
   *  Tally port is sent via x-tally-port header (see tally-local-proxy.js). */
  function tcProxyRequestUrl(urlStr) {
    var s = (urlStr || "").trim();
    if (!s) return "";
    try {
      var u = new URL(s);
      var path = u.pathname || "";
      if (u.search) path += u.search;
      if (u.hash) path += u.hash;
      if (!path || path === "/") path = "";
      return "http://127.0.0.1:" + TC_PROXY_PORT + path;
    } catch (e) {
      return "http://127.0.0.1:" + TC_PROXY_PORT;
    }
  }

  function tcSetProxyPortHeader(xhr, urlStr) {
    xhr.setRequestHeader("x-tally-port", tcTallyPortFromUrl(urlStr));
  }

  function loadPageContent(id) {
    if (!id) return;
    var url = "pages/" + id + ".html";

    fetch(url)
      .then(function (response) {
        if (!response.ok) {
          throw new Error("HTTP error " + response.status);
        }
        return response.text();
      })
      .then(function (html) {
        var $mount = $("#main-mount-point");
        $mount.html(html);

        var $page = $mount.find(".contentSection").first();

        var $fmtSel = $page.find('[data-id="payloadFormat"]');
        if ($fmtSel.length) {
          $fmtSel.val(tcSessionPayloadFormat);
        }

        // Run initializations for the loaded content
        resetTemplate($page);
        tcSyncHotBlocks($page, tcSessionPayloadFormat);

        mergePayloadsFromDom();

        var $pbFirst = $page.find(".page-body").first();
        if ($pbFirst.length) tcHidePageStatusAlert($pbFirst);

        // Inject the 3 global sub-label helper texts under Request URL / Validate / Payload Format
        tcInjectPageHelperTexts($page);
      })
      .catch(function (error) {
        $("#main-mount-point").html(
          '<div class="p-5 text-center text-danger"><h5>Error loading content.</h5>' +
          "<p>Make sure you are running a local web server (e.g., Live Server) to allow fetch API.</p></div>",
        );
        console.error("Fetch error:", error);
      });
  }

  $(".tabs").on("click", function (e) {
    if ($(e.target).closest(".sidebar-chevron").length) {
      return;
    }
    e.preventDefault();
    $(".tabs").removeClass("active");
    var selectedTab = $(this).attr("data-id");
    $(this).addClass("active");

    if (selectedTab) {
      window.history.replaceState(null, null, '#' + selectedTab);
    }

    tcRememberRequestUrl($('[data-id="requestUrl"]').val());
    loadPageContent(selectedTab);

    if (window.innerWidth < 992) {
      $("#sidebar").removeClass("show");
      $("#sidebarOverlay").removeClass("show");
      $("body").removeClass("overflow-hidden");
    }
  });

  // Delegated handler for .tabs links rendered inside dynamically loaded page content
  // (e.g. "Let's get started" CTA in tally-api-explorer.html).
  // The existing $(".tabs").on("click") is a direct binding — it only covers sidebar items
  // present at page load. This handles .tabs inside #main-mount-point loaded after that.
  $(document).on("click", "#main-mount-point .tabs", function (e) {
    e.preventDefault();
    var selectedTab = $(this).attr("data-id");
    if (!selectedTab) return;

    $(".tabs").removeClass("active");
    $('.tabs[data-id="' + selectedTab + '"]').addClass("active");
    window.history.replaceState(null, null, "#" + selectedTab);
    tcRememberRequestUrl($('[data-id="requestUrl"]').val());
    loadPageContent(selectedTab);

    if (window.innerWidth < 992) {
      $("#sidebar").removeClass("show");
      $("#sidebarOverlay").removeClass("show");
      $("body").removeClass("overflow-hidden");
    }
  });
  var hash = window.location.hash ? window.location.hash.substring(1) : "";
  var initialTab = "tally-api-explorer";
  if (hash && $('.tabs[data-id="' + hash + '"]').length > 0) {
    initialTab = hash;
    $(".tabs").removeClass("active");
    $('.tabs[data-id="' + hash + '"]').addClass("active");
  } else {
    initialTab = $(".tabs.active").first().attr("data-id") || "tally-api-explorer";
  }

  // Expand every parent collapse in the sidebar so the active item is visible
  // and the sidebar state matches what the user sees in the content area.
  tcExpandSidebarToActive(initialTab);
  loadPageContent(initialTab);

  /**
   * Walks up the sidebar DOM from the active tab element,
   * adds Bootstrap 'show' to every ancestor .collapse, and
   * rotates their chevron triggers to 0deg (expanded state).
   */
  function tcExpandSidebarToActive(tabId) {
    if (!tabId) return;
    var $activeItem = $('.tabs[data-id="' + tabId + '"]');
    if (!$activeItem.length) return;

    $activeItem.parents(".collapse").each(function () {
      var $collapseEl = $(this);
      $collapseEl.addClass("show");

      var id = $collapseEl.attr("id");
      if (!id) return;

      var $trigger = $('[data-bs-target="#' + id + '"]');
      var $chevron = $trigger.hasClass("sidebar-chevron")
        ? $trigger
        : $trigger.find(".sidebar-chevron");
      $chevron.css("transform", "rotate(0deg)");
    });
  }

  $("#sidebarToggle").on("click", function () {
    $("#sidebar").toggleClass("show");
    $("#sidebarOverlay").toggleClass("show");
    $("body").toggleClass("overflow-hidden");
  });

  $("#sidebarOverlay").on("click", function () {
    $("#sidebar").removeClass("show");
    $("#sidebarOverlay").removeClass("show");
    $("body").removeClass("overflow-hidden");
  });

  $(document).on("show.bs.collapse", '[class*="collapse"]', function () {
    var id = $(this).attr("id");
    if (id) {
      var $trigger = $('[data-bs-target="#' + id + '"]');
      var $chevron = $trigger.hasClass("sidebar-chevron") ? $trigger : $trigger.find(".sidebar-chevron");
      $chevron.css("transform", "rotate(0deg)");
    }
  });
  $(document).on("hide.bs.collapse", '[class*="collapse"]', function () {
    var id = $(this).attr("id");
    if (id) {
      var $trigger = $('[data-bs-target="#' + id + '"]');
      var $chevron = $trigger.hasClass("sidebar-chevron") ? $trigger : $trigger.find(".sidebar-chevron");
      $chevron.css("transform", "rotate(-90deg)");
    }
  });

  $('[data-bs-toggle="collapse"]').each(function () {
    var target = $(this).data("bs-target");
    var $trigger = $(this);
    var $chevron = $trigger.hasClass("sidebar-chevron") ? $trigger : $trigger.find(".sidebar-chevron");
    if ($(target).length && $(target).hasClass("show")) {
      $chevron.css("transform", "rotate(0deg)");
    } else {
      $chevron.css("transform", "rotate(-90deg)");
    }
  });

  var GENERIC_XML_SAMPLE =
    "<ENVELOPE>\n" +
    "  <HEADER>\n" +
    "    <TALLYREQUEST>Import Data</TALLYREQUEST>\n" +
    "  </HEADER>\n" +
    "  <BODY>\n" +
    "    <IMPORTDATA>\n" +
    "      <REQUESTDESC>\n" +
    "        <REPORTNAME>All Masters</REPORTNAME>\n" +
    "      </REQUESTDESC>\n" +
    "      <REQUESTDATA>\n" +
    "        <TALLYMESSAGE>\n" +
    "          <!-- Build your request here (ledger, group, voucher, etc.) -->\n" +
    "        </TALLYMESSAGE>\n" +
    "      </REQUESTDATA>\n" +
    "    </IMPORTDATA>\n" +
    "  </BODY>\n" +
    "</ENVELOPE>";

  /** JSON/XML bodies per section id (from JS). Missing sections pick up textarea JSON + generic XML on merge. */
  var REQUEST_PAYLOADS = {
    "create-ledger": {
      JSON: '{\n  "static_variables": [\n    {\n      "name": "svMstImportFormat",\n      "value": "jsonex"\n    },\n    {\n      "name": "svCurrentCompany",\n      "value": "Bhrama Enterprises"\n    }\n  ],\n  "tallymessage": [\n    {\n      "metadata": {\n        "type": "Ledger",\n        "action": "create",\n        "name": "Bank Of Baroda"\n      },\n      "name": "Bank Of Baroda",\n      "parent": "Bank Accounts"\n    }\n  ]\n}',

      XML: '<ENVELOPE>\n    <HEADER>\n        <VERSION>1</VERSION>\n        <TALLYREQUEST>Import</TALLYREQUEST>\n        <TYPE>Data</TYPE>\n        <ID>All Masters</ID>\n    </HEADER>\n    <BODY>\n        <DESC>\n            <STATICVARIABLES>\n                <SVMSTIMPORTFORMAT>XML</SVMSTIMPORTFORMAT>\n                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>\n            </STATICVARIABLES>\n            <TALLYMESSAGE>\n                <LEDGER NAME="Bank of Baroda" Action="Create">\n                    <NAME>Bank of Baroda</NAME>\n                    <PARENT> Bank Accounts </PARENT>\n                </LEDGER>\n            </TALLYMESSAGE>\n        </DESC>\n    </BODY>\n</ENVELOPE>',
    },
    "alter-ledger": {
      JSON: '{\n  "static_variables": [\n    {\n      "name": "svMstImportFormat",\n      "value": "jsonex"\n    },\n    {\n      "name": "svCurrentCompany",\n      "value": "Bhrama Enterprises"\n    }\n  ],\n  "tallymessage": [\n    {\n      "metadata": {\n        "type": "Ledger",\n        "action": "Alter",\n        "name": "Bank Of Baroda"\n      },\n      "Opening Balance": "3000"\n    }\n  ]\n}',

      XML: '<ENVELOPE>\n    <HEADER>\n        <VERSION>1</VERSION>\n        <TALLYREQUEST>Import</TALLYREQUEST>\n        <TYPE>Data</TYPE>\n        <ID>All Masters</ID>\n    </HEADER>\n    <BODY>\n        <DESC>\n            <STATICVARIABLES>\n                <SVMSTIMPORTFORMAT>XML</SVMSTIMPORTFORMAT>\n                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>\n            </STATICVARIABLES>\n            <TALLYMESSAGE>\n                <LEDGER NAME="Bank of Baroda" Action="Alter">\n                    <NAME>Bank of Baroda</NAME>\n                    <OPENINGBALANCE>30000</OPENINGBALANCE>\n                </LEDGER>\n            </TALLYMESSAGE>\n        </DESC>\n    </BODY>\n</ENVELOPE>',
    },
    "delete-ledger": {
      JSON: '{\n  "static_variables": [\n    {\n      "name": "svMstImportFormat",\n      "value": "jsonex"\n    },\n    {\n      "name": "svCurrentCompany",\n      "value": "Bhrama Enterprises"\n    }\n  ],\n  "tallymessage": [\n    {\n      "metadata": {\n        "type": "Ledger",\n        "action": "Delete",\n        "name": "Bank Of Baroda"\n      }\n    }\n  ]\n}',

      XML: '<ENVELOPE>\n    <HEADER>\n        <VERSION>1</VERSION>\n        <TALLYREQUEST>Import</TALLYREQUEST>\n        <TYPE>Data</TYPE>\n        <ID>All Masters</ID>\n    </HEADER>\n    <BODY>\n        <DESC>\n            <STATICVARIABLES>\n                <SVMSTIMPORTFORMAT>XML</SVMSTIMPORTFORMAT>\n                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>\n            </STATICVARIABLES>\n            <TALLYMESSAGE>\n                <LEDGER NAME="Bank of Baroda" Action="Delete">\n                    <NAME>Bank of Baroda</NAME>\n                </LEDGER>\n            </TALLYMESSAGE>\n        </DESC>\n    </BODY>\n</ENVELOPE>',
    },
    "pull-a-ledger": {
      JSON: '{\n  "static_variables": [\n    {\n      "name": "svExportFormat",\n      "value": "jsonEx"\n    },\n    {\n      "name": "svCurrentCompany",\n      "value": "Bhrama Enterprises"\n    }\n  ],\n  "fetch_list": [\n    "Name",\n    "Parent",\n    "Opening Balance",\n    "Closing Balance"\n  ]\n}',

      XML: '<ENVELOPE>\n    <HEADER>\n        <VERSION>1</VERSION>\n        <TALLYREQUEST>Export</TALLYREQUEST>\n        <TYPE>Object</TYPE>\n        <SUBTYPE>Ledger</SUBTYPE>\n        <ID TYPE="Name">Kotak Bank</ID>\n    </HEADER>\n    <BODY>\n        <DESC>\n            <STATICVARIABLES>\n                <SVEXPORTFORMAT>XML</SVEXPORTFORMAT>\n                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>\n            </STATICVARIABLES>\n            <FETCHLIST>\n                <FETCH>Name</FETCH>\n                <FETCH>Parent</FETCH>\n                <FETCH>Opening Balance</FETCH>\n                <FETCH>Closing Balance</FETCH>\n            </FETCHLIST>\n        </DESC>\n    </BODY>\n</ENVELOPE>',
    },
    "pull-all-ledger": {
      JSON: '{\n  "static_variables": [\n    {\n      "name": "svExportFormat",\n      "value": "jsonex"\n    },\n    {\n      "name": "svCurrentCompany",\n      "value": "Bhrama Enterprises"\n    }\n  ]\n}',

      XML: "<ENVELOPE>\n    <HEADER>\n        <VERSION>1</VERSION>\n        <TALLYREQUEST>Export</TALLYREQUEST>\n        <TYPE>Collection</TYPE>\n        <ID>Ledger</ID>\n    </HEADER>\n    <BODY>\n        <DESC>\n            <STATICVARIABLES>\n                <SVEXPORTFORMAT>XML</SVEXPORTFORMAT>\n                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>\n            </STATICVARIABLES>\n        </DESC>\n    </BODY>\n</ENVELOPE>",
    },
    "pull-ledgers-of-group": {
      JSON: '{\n  "static_variables": [\n    {\n      "name": "svExportFormat",\n      "value": "jsonex"\n    },\n    {\n      "name": "svCurrentCompany",\n      "value": "Bhrama Enterprises"\n    }\n  ],\n  "tdlmessage": [\n    {\n      "definitions": [\n        {\n          "metadata": {\n            "name": "TSPLBankLedgers",\n            "type": "Collection"\n          },\n          "attributes": [\n            {\n              "Type": "Ledger"\n            },\n            {\n              "Child Of": "$$GroupBank"\n            },\n            {\n              "Native Method": "Name, Parent, OpeningBalance, ClosingBalance, IseBankingEnabled, Mailing Name, Bank Details"\n            }\n          ]\n        }\n      ]\n    }\n  ]\n}',

      XML: '<ENVELOPE>\n    <HEADER>\n        <VERSION>1</VERSION>\n        <TALLYREQUEST>Export</TALLYREQUEST>\n        <TYPE>Collection</TYPE>\n        <ID>TSPLBankLedgers</ID>\n    </HEADER>\n    <BODY>\n        <DESC>\n            <STATICVARIABLES>\n                <SVEXPORTFORMAT>XML</SVEXPORTFORMAT>\n                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>\n            </STATICVARIABLES>\n            <TDL>\n                <TDLMESSAGE>\n                    <COLLECTION NAME="TSPLBankLedgers" ISMODIFY="No" ISFIXED="No" ISINITIALIZE="No" ISOPTION="No" ISINTERNAL="No">\n                        <TYPE>Ledger</TYPE>\n                        <CHILDOF>$$GroupBank</CHILDOF>\n                        <NATIVEMETHOD>Name, Parent, OpeningBalance, ClosingBalance, IseBankingEnabled, Mailing Name, Bank Details</NATIVEMETHOD>\n                    </COLLECTION>\n                </TDLMESSAGE>\n            </TDL>\n        </DESC>\n    </BODY>\n</ENVELOPE>',
    },
    /* Group */
    "create-group": {
      JSON: '{\n  "static_variables": [\n    {\n      "name": "svMstImportFormat",\n      "value": "jsonex"\n    },\n    {\n      "name": "svCurrentCompany",\n      "value": "Bhrama Enterprises"\n    }\n  ],\n  "tallymessage": [\n    {\n      "metadata": {\n        "type": "Group",\n        "action": "create",\n        "name": "North Bank Accounts"\n      },\n      "name": "North Bank Accounts",\n      "parent": "Bank Accounts"\n    }\n  ]\n}',
      XML: '<ENVELOPE>\n    <HEADER>\n        <VERSION>1</VERSION>\n        <TALLYREQUEST>Import</TALLYREQUEST>\n        <TYPE>Data</TYPE>\n        <ID>All Masters</ID>\n    </HEADER>\n    <BODY>\n        <DESC>\n            <STATICVARIABLES>\n                <SVMSTIMPORTFORMAT>XML</SVMSTIMPORTFORMAT>\n                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>\n            </STATICVARIABLES>\n            <TALLYMESSAGE xmlns:UDF="TallyUDF">\n                <GROUP NAME="North Bank Accounts" Action="Create">\n                    <NAME>North Bank Accounts</NAME>\n                    <PARENT>Bank Accounts</PARENT>\n                </GROUP>\n            </TALLYMESSAGE>\n        </DESC>\n    </BODY>\n</ENVELOPE>',
    },
    "alter-group": {
      JSON: '{\n  "static_variables": [\n    {\n      "name": "svMstImportFormat",\n      "value": "jsonex"\n    },\n    {\n      "name": "svCurrentCompany",\n      "value": "Bhrama Enterprises"\n    }\n  ],\n  "tallymessage": [\n    {\n      "metadata": {\n        "type": "Group",\n        "action": "Alter",\n        "name": "North Bank Accounts"\n      },\n      "name": "North Bank Accounts",\n      "IsSubLedger": "yes"\n    }\n  ]\n}',
      XML: '<ENVELOPE>\n    <HEADER>\n        <VERSION>1</VERSION>\n        <TALLYREQUEST>Import</TALLYREQUEST>\n        <TYPE>Data</TYPE>\n        <ID>All Masters</ID>\n    </HEADER>\n    <BODY>\n        <DESC>\n            <STATICVARIABLES>\n                <SVMSTIMPORTFORMAT>XML</SVMSTIMPORTFORMAT>\n                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>\n            </STATICVARIABLES>\n            <TALLYMESSAGE xmlns:UDF="TallyUDF">\n                <GROUP NAME="North Bank Accounts" Action="Alter">\n                    <NAME>North Bank Accounts</NAME>\n                    <ISSUBLEDGER>Yes</ISSUBLEDGER>\n                </GROUP>\n            </TALLYMESSAGE>\n        </DESC>\n    </BODY>\n</ENVELOPE>',
    },
    "delete-group": {
      JSON: '{\n  "static_variables": [\n    {\n      "name": "svMstImportFormat",\n      "value": "jsonex"\n    },\n    {\n      "name": "svCurrentCompany",\n      "value": "Bhrama Enterprises"\n    }\n  ],\n  "tallymessage": [\n    {\n      "metadata": {\n        "type": "Group",\n        "action": "Delete",\n        "name": "North Bank Accounts"\n      }\n    }\n  ]\n}',
      XML: '<ENVELOPE>\n    <HEADER>\n        <VERSION>1</VERSION>\n        <TALLYREQUEST>Import</TALLYREQUEST>\n        <TYPE>Data</TYPE>\n        <ID>All Masters</ID>\n    </HEADER>\n    <BODY>\n        <DESC>\n            <STATICVARIABLES>\n                <SVMSTIMPORTFORMAT>XML</SVMSTIMPORTFORMAT>\n                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>\n            </STATICVARIABLES>\n            <TALLYMESSAGE xmlns:UDF="TallyUDF">\n                <GROUP NAME="North Bank Accounts" Action="Delete">\n                    <NAME>North Bank Accounts</NAME>\n                </GROUP>\n            </TALLYMESSAGE>\n        </DESC>\n    </BODY>\n</ENVELOPE>',
    },
    "pull-group": {
      JSON: '{\n  "static_variables": [\n    {\n      "name": "svExportFormat",\n      "value": "jsonEx"\n    },\n    {\n      "name": "svCurrentCompany",\n      "value": "Bhrama Enterprises"\n    }\n  ],\n  "fetch_list": [\n    "Name",\n    "Parent",\n    "Parent Hierarchy",\n    "Opening Balance",\n    "Closing Balance"\n  ]\n}',
      XML: '<ENVELOPE>\n    <HEADER>\n        <VERSION>1</VERSION>\n        <TALLYREQUEST>Export</TALLYREQUEST>\n        <TYPE>Object</TYPE>\n        <SUBTYPE>Group</SUBTYPE>\n        <ID TYPE="Name">Bank Accounts</ID>\n    </HEADER>\n    <BODY>\n        <DESC>\n            <STATICVARIABLES>\n                <SVEXPORTFORMAT>XML</SVEXPORTFORMAT>\n                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>\n            </STATICVARIABLES>\n            <FETCHLIST>\n                <FETCH>Name</FETCH>\n                <FETCH>Parent</FETCH>\n                <FETCH>Parent Hierarchy</FETCH>\n                <FETCH>Opening Balance</FETCH>\n                <FETCH>Closing Balance</FETCH>\n            </FETCHLIST>\n        </DESC>\n    </BODY>\n</ENVELOPE>',
    },
    "pull-all-groups": {
      JSON: '{\n  "static_variables": [\n    {\n      "name": "svExportFormat",\n      "value": "jsonex"\n    },\n    {\n      "name": "svCurrentCompany",\n      "value": "Bhrama Enterprises"\n    }\n  ]\n}',
      XML: "<ENVELOPE>\n    <HEADER>\n        <VERSION>1</VERSION>\n        <TALLYREQUEST>Export</TALLYREQUEST>\n        <TYPE>Collection</TYPE>\n        <ID>Group</ID>\n    </HEADER>\n    <BODY>\n        <DESC>\n            <STATICVARIABLES>\n                <SVEXPORTFORMAT>XML</SVEXPORTFORMAT>\n                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>\n            </STATICVARIABLES>\n        </DESC>\n    </BODY>\n</ENVELOPE>",
    },
    "pull-groups-of-group": {
      JSON: '{\n  "static_variables": [\n    {\n      "name": "svExportFormat",\n      "value": "jsonex"\n    },\n    {\n      "name": "svCurrentCompany",\n      "value": "Bhrama Enterprises"\n    }\n  ],\n  "tdlmessage": [\n    {\n      "definitions": [\n        {\n          "metadata": {\n            "name": "TSPLAssetGroups",\n            "type": "Collection"\n          },\n          "attributes": [\n            {\n              "Type": "Group"\n            },\n            {\n              "Child Of": "$$GroupCurrentAssets"\n            },\n            {\n              "Belongs To": "Yes"\n            },\n            {\n              "Native Method": "Name, Parent, IsSubledger, IsRevenue, Parent Hierarchy"\n            }\n          ]\n        }\n      ]\n    }\n  ]\n}',
      XML: '<ENVELOPE>\n    <HEADER>\n        <VERSION>1</VERSION>\n        <TALLYREQUEST>Export</TALLYREQUEST>\n        <TYPE>Collection</TYPE>\n        <ID>TSPLAssetGroups</ID>\n    </HEADER>\n    <BODY>\n        <DESC>\n            <STATICVARIABLES>\n                <SVEXPORTFORMAT>XML</SVEXPORTFORMAT>\n                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>\n            </STATICVARIABLES>\n            <TDL>\n                <TDLMESSAGE>\n                    <COLLECTION NAME="TSPLAssetGroups">\n                        <TYPE>Group</TYPE>\n                        <CHILDOF>$$GroupCurrentAssets</CHILDOF>\n                        <BELONGSTO>Yes</BELONGSTO>\n                        <NATIVEMETHOD>Name, Parent, IsSubledger, IsRevenue, Parent Hierarchy</NATIVEMETHOD>\n                    </COLLECTION>\n                </TDLMESSAGE>\n            </TDL>\n        </DESC>\n    </BODY>\n</ENVELOPE>',
    },
    /* Stock Items */
    "create-stock-item": {
      JSON: '{\n  "static_variables": [\n    {\n      "name": "svMstImportFormat",\n      "value": "jsonex"\n    },\n    {\n      "name": "svCurrentCompany",\n      "value": "Bhrama Enterprises"\n    }\n  ],\n  "tallymessage": [\n    {\n      "metadata": {\n        "type": "Stock Item",\n        "name": "Tea Powder",\n        "action": "create"\n      },\n      "name": "Tea Powder",\n      "parent": "\\u0004 Primary",\n      "base units": "nos"\n    }\n  ]\n}',

      XML: '<ENVELOPE>\n    <HEADER>\n        <VERSION>1</VERSION>\n        <TALLYREQUEST>Import</TALLYREQUEST>\n        <TYPE>Data</TYPE>\n        <ID>All Masters</ID>\n    </HEADER>\n    <BODY>\n        <DESC>\n            <STATICVARIABLES>\n                <SVMSTIMPORTFORMAT>XML</SVMSTIMPORTFORMAT>\n                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>\n            </STATICVARIABLES>\n            <TALLYMESSAGE>\n                <StockItem NAME="Tea Powder" Action="Create">\n                    <NAME>Tea Powder</NAME>\n                    <PARENT>&#4; Primary</PARENT>\n                    <BaseUnits>nos</BaseUnits>\n                </StockItem>\n            </TALLYMESSAGE>\n        </DESC>\n</BODY>\n</ENVELOPE>',
    },
    "alter-stock-item": {
      JSON: '{\n  "static_variables": [\n    {\n      "name": "svMstImportFormat",\n      "value": "jsonex"\n    },\n    {\n      "name": "svCurrentCompany",\n      "value": "Bhrama Enterprises"\n    }\n  ],\n  "tallymessage": [\n    {\n      "metadata": {\n        "type": "Stock Item",\n        "name": "Tea Powder",\n        "action": "Alter"\n      },\n      "opening balance": " 200 nos"\n    }\n  ]\n}',

      XML: '<ENVELOPE>\n    <HEADER>\n        <VERSION>1</VERSION>\n        <TALLYREQUEST>Import</TALLYREQUEST>\n        <TYPE>Data</TYPE>\n        <ID>All Masters</ID>\n    </HEADER>\n    <BODY>\n        <DESC>\n            <STATICVARIABLES>\n                <SVMSTIMPORTFORMAT>XML</SVMSTIMPORTFORMAT>\n                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>\n            </STATICVARIABLES>\n            <TALLYMESSAGE>\n                <StockItem NAME="Tea Powder" Action="Alter">\n                    <NAME> Tea Powder </NAME>\n                    <OPENINGBALANCE>200 NOS</OPENINGBALANCE>\n                </StockItem>\n            </TALLYMESSAGE>\n        </DESC>\n</BODY>\n</ENVELOPE>',
    },
    "delete-stock-item": {
      JSON: '{\n  "static_variables": [\n    {\n      "name": "svMstImportFormat",\n      "value": "jsonex"\n    },\n    {\n      "name": "svCurrentCompany",\n      "value": "Bhrama Enterprises"\n    }\n  ],\n  "tallymessage": [\n    {\n      "metadata": {\n        "type": "Stock Item",\n        "name": "Tea Powder",\n        "action": "Delete"\n      }\n    }\n  ]\n}',

      XML: '<ENVELOPE>\n    <HEADER>\n        <VERSION>1</VERSION>\n        <TALLYREQUEST>Import</TALLYREQUEST>\n        <TYPE>Data</TYPE>\n        <ID>All Masters</ID>\n    </HEADER>\n    <BODY>\n        <DESC>\n            <STATICVARIABLES>\n                <SVMSTIMPORTFORMAT>XML</SVMSTIMPORTFORMAT>\n                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>\n            </STATICVARIABLES>\n            <TALLYMESSAGE>\n                <StockItem NAME="Tea Powder" Action="Delete">\n                    <NAME> Tea Powder </NAME>\n                </StockItem>\n            </TALLYMESSAGE>\n        </DESC>\n</BODY>\n</ENVELOPE>',
    },
    "pull-stock-item": {
      JSON: '{\n  "static_variables": [\n    {\n      "name": "svExportFormat",\n      "value": "jsonEx"\n    },\n    {\n      "name": "svCurrentCompany",\n      "value": "Bhrama Enterprises"\n    }\n  ],\n  "fetch_list": [\n    "Name",\n    "Parent",\n    "Opening Balance",\n    "Closing Balance"\n  ]\n}',

      XML: '<ENVELOPE>\n    <HEADER>\n        <VERSION>1</VERSION>\n        <TALLYREQUEST>Export</TALLYREQUEST>\n        <TYPE>Object</TYPE>\n        <SUBTYPE>Stock Item</SUBTYPE>\n        <ID TYPE="Name">Coffee Powder</ID>\n    </HEADER>\n    <BODY>\n        <DESC>\n            <STATICVARIABLES>\n                <SVEXPORTFORMAT>XML</SVEXPORTFORMAT>\n                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>\n            </STATICVARIABLES>\n            <FETCHLIST>\n                <FETCH>Name</FETCH>\n                <FETCH>Parent</FETCH>\n                <FETCH>BaseUnits</FETCH>\n                <FETCH>Closing Balance</FETCH>\n            </FETCHLIST>\n        </DESC>\n    </BODY>\n</ENVELOPE>',
    },
    "pull-all-stock-items": {
      JSON: '{\n  "static_variables": [\n    {\n      "name": "svExportFormat",\n      "value": "jsonex"\n    },\n    {\n      "name": "svCurrentCompany",\n      "value": "Bhrama Enterprises"\n    }\n  ]\n}',

      XML: "<ENVELOPE>\n    <HEADER>\n        <VERSION>1</VERSION>\n        <TALLYREQUEST>Export</TALLYREQUEST>\n        <TYPE>Collection</TYPE>\n        <ID>StockItem</ID>\n    </HEADER>\n    <BODY>\n        <DESC>\n            <STATICVARIABLES>\n                <SVEXPORTFORMAT>XML</SVEXPORTFORMAT>\n                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>\n            </STATICVARIABLES>\n        </DESC>\n    </BODY>\n</ENVELOPE>",
    },
    "pull-stock-items-of-stock-group": {
      JSON: '{\n  "static_variables": [\n    {\n      "name": "svExportFormat",\n      "value": "jsonex"\n    },\n    {\n      "name": "svCurrentCompany",\n      "value": "Bhrama Enterprises"\n    }\n  ],\n  "tdlmessage": [\n    {\n      "definitions": [\n        {\n          "metadata": {\n            "name": "TSPLStockOfGroup",\n            "type": "Collection"\n          },\n          "attributes": [\n            {\n              "Type": "StockItem"\n            },\n            {\n              "Child Of": "\\\"Gadgets\\\""\n            },\n            {\n              "Native Method": "Name, Parent, ClosingBalance, ClosingValue, BaseUnits"\n            }\n          ]\n        }\n      ]\n    }\n  ]\n}',

      XML: '<ENVELOPE>\n    <HEADER>\n        <VERSION>1</VERSION>\n        <TALLYREQUEST>Export</TALLYREQUEST>\n        <TYPE>Collection</TYPE>\n        <ID>TSPLStockOfGroup</ID>\n    </HEADER>\n    <BODY>\n        <DESC>\n            <STATICVARIABLES>\n                <SVEXPORTFORMAT>XML</SVEXPORTFORMAT>\n                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>\n            </STATICVARIABLES>\n<TDL>\n<TDLMESSAGE>\n  <COLLECTION NAME="TSPLStockOfGroup" ISMODIFY="No" ISFIXED="No" ISINITIALIZE="No" ISOPTION="No" ISINTERNAL="No">\n   <TYPE>StockItem</TYPE>\n   <CHILDOF>&quot;Gadgets&quot;</CHILDOF>\n   <NATIVEMETHOD>Name, Parent, ClosingBalance, ClosingValue, BaseUnits</NATIVEMETHOD>\n  </COLLECTION>\n</TDLMESSAGE>\n</TDL>\n        </DESC>\n    </BODY>\n</ENVELOPE>',
    },
    /* Stock Groups */
    "create-stock-group": {
      JSON: '{\n  "static_variables": [\n    {\n      "name": "svMstImportFormat",\n      "value": "jsonex"\n    },\n    {\n      "name": "svCurrentCompany",\n      "value": "Bhrama Enterprises"\n    }\n  ],\n  "tallymessage": [\n    {\n      "metadata": {\n        "type": "Stock Group",\n        "action": "create",\n        "name": "Tea Products"\n      },\n      "name": "Tea Products"\n    }\n  ]\n}',

      XML: '<ENVELOPE>\n    <HEADER>\n        <VERSION>1</VERSION>\n        <TALLYREQUEST>Import</TALLYREQUEST>\n        <TYPE>Data</TYPE>\n        <ID>All Masters</ID>\n    </HEADER>\n    <BODY>\n        <DESC>\n            <STATICVARIABLES>\n                <SVMSTIMPORTFORMAT>XML</SVMSTIMPORTFORMAT>\n                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>\n            </STATICVARIABLES>\n<TALLYMESSAGE xmlns:UDF="TallyUDF">\n <STOCKGROUP NAME="Tea Products" Action="Create">\n  <NAME>Tea Products</NAME>\n </STOCKGROUP>\n</TALLYMESSAGE>\n</DESC>\n</BODY>\n</ENVELOPE>',
    },
    "alter-stock-group": {
      JSON: '{\n  "static_variables": [\n    {\n      "name": "svMstImportFormat",\n      "value": "jsonex"\n    },\n    {\n      "name": "svCurrentCompany",\n      "value": "Bhrama Enterprises"\n    }\n  ],\n  "tallymessage": [\n    {\n      "metadata": {\n        "type": "Stock Group",\n        "action": "Alter",\n        "name": "Tea Products"\n      },\n      "name": "Tea Products",\n      "isaddable": "Yes"\n    }\n  ]\n}',

      XML: '<ENVELOPE>\n    <HEADER>\n        <VERSION>1</VERSION>\n        <TALLYREQUEST>Import</TALLYREQUEST>\n        <TYPE>Data</TYPE>\n        <ID>All Masters</ID>\n    </HEADER>\n    <BODY>\n        <DESC>\n            <STATICVARIABLES>\n                <SVMSTIMPORTFORMAT>XML</SVMSTIMPORTFORMAT>\n                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>\n            </STATICVARIABLES>\n<TALLYMESSAGE xmlns:UDF="TallyUDF">\n <STOCKGROUP NAME="Tea Products" Action="Alter">\n  <NAME>Tea Products</NAME>\n  <ISADDABLE>Yes</ISADDABLE>\n </STOCKGROUP>\n</TALLYMESSAGE>\n</DESC>\n</BODY>\n</ENVELOPE>',
    },
    "delete-stock-group": {
      JSON: '{\n  "static_variables": [\n    {\n      "name": "svMstImportFormat",\n      "value": "jsonex"\n    },\n    {\n      "name": "svCurrentCompany",\n      "value": "Bhrama Enterprises"\n    }\n  ],\n  "tallymessage": [\n    {\n      "metadata": {\n        "type": "Stock Group",\n        "action": "Delete",\n        "name": "Tea Products"\n      }\n    }\n  ]\n}',

      XML: '<ENVELOPE>\n    <HEADER>\n        <VERSION>1</VERSION>\n        <TALLYREQUEST>Import</TALLYREQUEST>\n        <TYPE>Data</TYPE>\n        <ID>All Masters</ID>\n    </HEADER>\n    <BODY>\n        <DESC>\n            <STATICVARIABLES>\n                <SVMSTIMPORTFORMAT>XML</SVMSTIMPORTFORMAT>\n                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>\n            </STATICVARIABLES>\n<TALLYMESSAGE xmlns:UDF="TallyUDF">\n <STOCKGROUP NAME="Tea Products" Action="Delete">\n  <NAME>Tea Products</NAME>\n </STOCKGROUP>\n</TALLYMESSAGE>\n</DESC>\n</BODY>\n</ENVELOPE>',
    },
    "pull-stock-group": {
      JSON: '{\n  "static_variables": [\n    {\n      "name": "svExportFormat",\n      "value": "jsonEx"\n    },\n    {\n      "name": "svCurrentCompany",\n      "value": "Bhrama Enterprises"\n    }\n  ],\n  "fetch_list": [\n    "Name",\n    "Parent",\n    "Opening Balance",\n    "Closing Balance"\n  ]\n}',

      XML: '<ENVELOPE>\n    <HEADER>\n        <VERSION>1</VERSION>\n        <TALLYREQUEST>Export</TALLYREQUEST>\n        <TYPE>Object</TYPE>\n        <SUBTYPE>Stock Group</SUBTYPE>\n        <ID TYPE="Name">Laptops</ID>\n    </HEADER>\n    <BODY>\n        <DESC>\n            <STATICVARIABLES>\n                <SVEXPORTFORMAT>XML</SVEXPORTFORMAT>\n                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>\n            </STATICVARIABLES>\n            <FETCHLIST>\n                <FETCH>Name</FETCH>\n                <FETCH>Parent</FETCH>\n                <FETCH>Opening Balance</FETCH>\n                <FETCH>Closing Balance</FETCH>\n            </FETCHLIST>\n        </DESC>\n    </BODY>\n</ENVELOPE>',
    },
    "pull-all-stock-groups": {
      JSON: '{\n  "static_variables": [\n    {\n      "name": "svExportFormat",\n      "value": "jsonex"\n    },\n    {\n      "name": "svCurrentCompany",\n      "value": "Bhrama Enterprises"\n    }\n  ]\n}',

      XML: "<ENVELOPE>\n    <HEADER>\n        <VERSION>1</VERSION>\n        <TALLYREQUEST>Export</TALLYREQUEST>\n        <TYPE>Collection</TYPE>\n        <ID>StockGroup</ID>\n    </HEADER>\n    <BODY>\n        <DESC>\n            <STATICVARIABLES>\n                <SVEXPORTFORMAT>XML</SVEXPORTFORMAT>\n                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>\n            </STATICVARIABLES>\n        </DESC>\n    </BODY>\n</ENVELOPE>",
    },
    "pull-stock-group-zero-balance": {
      JSON: '{\n  "static_variables": [\n    {\n      "name": "svExportFormat",\n      "value": "jsonex"\n    },\n    {\n      "name": "svCurrentCompany",\n      "value": "Bhrama Enterprises"\n    }\n  ],\n  "tdlmessage": [\n    {\n      "definitions": [\n        {\n          "metadata": {\n            "name": "TSPL Stock Group ZeroBal",\n            "type": "Collection"\n          },\n          "attributes": [\n            {\n              "Type": "StockGroup"\n            },\n            {\n              "Native Method": "Name, Parent, Openingbalance, ClosingBalance"\n            },\n            {\n              "Filters": "TSPL Zero Closing"\n            }\n          ]\n        },\n        {\n          "metadata": {\n            "name": "TSPL ZeroClosing",\n            "type": "System",\n            "sys_type": "Formulae"\n          },\n          "value": "$ClosingBalance = 0"\n        }\n      ]\n    }\n  ]\n}',

      XML: '<ENVELOPE>\n    <HEADER>\n        <VERSION>1</VERSION>\n        <TALLYREQUEST>Export</TALLYREQUEST>\n        <TYPE>Collection</TYPE>\n        <ID>TSPL Stock Group ZeroBal</ID>\n    </HEADER>\n    <BODY>\n        <DESC>\n            <STATICVARIABLES>\n                <SVEXPORTFORMAT>XML</SVEXPORTFORMAT>\n                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>\n            </STATICVARIABLES>\n            <TDL>\n<TDLMESSAGE>\n  <COLLECTION NAME="TSPL Stock Group ZeroBal" ISMODIFY="No" ISFIXED="No" ISINITIALIZE="No" ISOPTION="No" ISINTERNAL="No">\n   <TYPE>StockGroup</TYPE>\n   <NATIVEMETHOD>Name, Parent, Openingbalance, ClosingBalance</NATIVEMETHOD>\n   <FILTERS>TSPL Zero Closing</FILTERS>\n  </COLLECTION>\n  <SYSTEM TYPE="Formulae" NAME="TSPL ZeroClosing" ISMODIFY="No" ISFIXED="No" ISINTERNAL="No">$ClosingBalance = 0  </SYSTEM>\n</TDLMESSAGE>\n</TDL>\n        </DESC>\n    </BODY>\n</ENVELOPE>',
    },
    /* Units */
    "create-simple-unit": {
      JSON: '{\n  "static_variables": [\n    {\n      "name": "svMstImportFormat",\n      "value": "jsonex"\n    },\n    {\n      "name": "svCurrentCompany",\n      "value": "Bhrama Enterprises"\n    }\n  ],\n  "tallymessage": [\n    {\n      "metadata": {\n        "type": "Unit",\n        "action": "create",\n        "name": "box"\n      },\n      "name": "box",\n      "originalname": "boxes",\n      "issimpleunit": true\n    }\n  ]\n}',

      XML: '<ENVELOPE>\n   <HEADER>\n      <VERSION>1</VERSION>\n      <TALLYREQUEST>Import</TALLYREQUEST>\n      <TYPE>Data</TYPE>\n      <ID>All Masters</ID>\n   </HEADER>\n   <BODY>\n      <DESC>\n         <STATICVARIABLES>\n            <SVMSTIMPORTFORMAT>XML</SVMSTIMPORTFORMAT>\n            <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>\n         </STATICVARIABLES>\n<TALLYMESSAGE xmlns:UDF="TallyUDF">\n <UNIT NAME="Box" ACTION="Create">\n  <NAME>Box</NAME>\n  <ISSIMPLEUNIT>Yes</ISSIMPLEUNIT>\n  <ORIGINALNAME>Boxes</ORIGINALNAME>\n </UNIT>\n</TALLYMESSAGE>\n      </DESC>\n   </BODY>\n</ENVELOPE>',
    },
    "create-compound-unit": {
      JSON: '{\n  "static_variables": [\n    {\n      "name": "svMstImportFormat",\n      "value": "jsonex"\n    },\n    {\n      "name": "svCurrentCompany",\n      "value": "Bhrama Enterprises"\n    }\n  ],\n  "tallymessage": [\n    {\n      "metadata": {\n        "type": "Unit",\n        "action": "create",\n        "name": "KG of 1000 gm"\n      },\n      "name": "KG of 1000 gm",\n      "baseunits": "Kg",\n      "additionalunits": "gm",\n      "issimpleunit": false,\n      "conversion": " 1000"\n    }\n  ]\n}',

      XML: '<ENVELOPE>\n    <HEADER>\n        <VERSION>1</VERSION>\n        <TALLYREQUEST>Import</TALLYREQUEST>\n        <TYPE>Data</TYPE>\n        <ID>All Masters</ID>\n    </HEADER>\n    <BODY>\n        <DESC>\n            <STATICVARIABLES>\n                <SVMSTIMPORTFORMAT>XML</SVMSTIMPORTFORMAT>\n                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>\n            </STATICVARIABLES>\n<TALLYMESSAGE xmlns:UDF="TallyUDF">\n <UNIT NAME="Kg of 1000 gm" ACTION="Create">\n  <NAME>Kg of 1000 gm</NAME>\n  <BASEUNITS>Kg</BASEUNITS>\n  <ADDITIONALUNITS>gm</ADDITIONALUNITS>\n  <ISSIMPLEUNIT>No</ISSIMPLEUNIT>\n  <CONVERSION> 1000</CONVERSION>\n </UNIT>\n</TALLYMESSAGE>\n        </DESC>\n    </BODY>\n</ENVELOPE>',
    },
    "alter-unit": {
      JSON: '{\n  "static_variables": [\n    {\n      "name": "svMstImportFormat",\n      "value": "jsonex"\n    },\n    {\n      "name": "svCurrentCompany",\n      "value": "Bhrama Enterprises"\n    }\n  ],\n  "tallymessage": [\n    {\n      "metadata": {\n        "type": "Unit",\n        "action": "Alter",\n        "name": "box"\n      },\n      "name": "box",\n      "decimalplaces": " 2"\n    }\n  ]\n}',

      XML: '<ENVELOPE>\n    <HEADER>\n        <VERSION>1</VERSION>\n        <TALLYREQUEST>Import</TALLYREQUEST>\n        <TYPE>Data</TYPE>\n        <ID>All Masters</ID>\n    </HEADER>\n    <BODY>\n        <DESC>\n            <STATICVARIABLES>\n                <SVMSTIMPORTFORMAT>XML</SVMSTIMPORTFORMAT>\n                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>\n            </STATICVARIABLES>\n<TALLYMESSAGE xmlns:UDF="TallyUDF">\n <UNIT NAME="Box" ACTION="Alter">\n  <NAME>Box</NAME>\n  <DECIMALPLACES>2</DECIMALPLACES>\n </UNIT>\n</TALLYMESSAGE>\n        </DESC>\n    </BODY>\n</ENVELOPE>',
    },
    "delete-unit": {
      JSON: '{\n  "static_variables": [\n    {\n      "name": "svMstImportFormat",\n      "value": "jsonex"\n    },\n    {\n      "name": "svCurrentCompany",\n      "value": "Bhrama Enterprises"\n    }\n  ],\n  "tallymessage": [\n    {\n      "metadata": {\n        "type": "Unit",\n        "action": "Delete",\n        "name": "box"\n      }\n    }\n  ]\n}',

      XML: '<ENVELOPE>\n    <HEADER>\n        <VERSION>1</VERSION>\n        <TALLYREQUEST>Import</TALLYREQUEST>\n        <TYPE>Data</TYPE>\n        <ID>All Masters</ID>\n    </HEADER>\n    <BODY>\n        <DESC>\n            <STATICVARIABLES>\n                <SVMSTIMPORTFORMAT>XML</SVMSTIMPORTFORMAT>\n                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>\n            </STATICVARIABLES>\n<TALLYMESSAGE xmlns:UDF="TallyUDF">\n <UNIT NAME="Box" ACTION="Delete">\n  <NAME>Box</NAME>\n </UNIT>\n</TALLYMESSAGE>\n        </DESC>\n    </BODY>\n</ENVELOPE>',
    },
    "pull-unit": {
      JSON: '{\n  "static_variables": [\n    {\n      "name": "svExportFormat",\n      "value": "jsonEx"\n    },\n    {\n      "name": "svCurrentCompany",\n      "value": "Bhrama Enterprises"\n    }\n  ],\n  "fetch_list": [\n    "Name"\n  ]\n}',

      XML: '<ENVELOPE>\n    <HEADER>\n        <VERSION>1</VERSION>\n        <TALLYREQUEST>Export</TALLYREQUEST>\n        <TYPE>Object</TYPE>\n        <SUBTYPE>Unit</SUBTYPE>\n        <ID TYPE="Name">Nos</ID>\n    </HEADER>\n    <BODY>\n        <DESC>\n            <STATICVARIABLES>\n                <SVEXPORTFORMAT>XML</SVEXPORTFORMAT>\n                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>\n            </STATICVARIABLES>\n            <FETCHLIST>\n                <FETCH>Name</FETCH>\n            </FETCHLIST>\n        </DESC>\n    </BODY>\n</ENVELOPE>',
    },
    "pull-all-units": {
      JSON: '{\n  "static_variables": [\n    {\n      "name": "svExportFormat",\n      "value": "jsonex"\n    },\n    {\n      "name": "svCurrentCompany",\n      "value": "Bhrama Enterprises"\n    }\n  ]\n}',

      XML: '<ENVELOPE>\n    <HEADER>\n        <VERSION>1</VERSION>\n        <TALLYREQUEST>Export</TALLYREQUEST>\n        <TYPE>Collection</TYPE>\n        <ID>TSPLSimpleUnits</ID>\n    </HEADER>\n    <BODY>\n        <DESC>\n            <STATICVARIABLES>\n                <SVEXPORTFORMAT>XML</SVEXPORTFORMAT>\n                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>\n            </STATICVARIABLES>\n<TDL>\n<TDLMESSAGE>\n  <COLLECTION NAME="TSPL SimpleUnits" ISMODIFY="No" ISFIXED="No" ISINITIALIZE="No" ISOPTION="No" ISINTERNAL="No">\n   <TYPE>Unit</TYPE>\n   <NATIVEMETHOD>Name, OriginalName, IsSimpleUnit</NATIVEMETHOD>\n   <FILTERS>TSPLSimpleUnitsOnly</FILTERS>\n  </COLLECTION>\n  <SYSTEM TYPE="Formulae" NAME="TSPLSimpleUnitsOnly" ISMODIFY="No" ISFIXED="No" ISINTERNAL="No">$IsSimpleUnit  </SYSTEM>\n</TDLMESSAGE>\n</TDL>\n        </DESC>\n    </BODY>\n</ENVELOPE>',
    },
    /* Payment */
    "payment-create-banking": {
      JSON: '{\n  "static_variables": [\n    {\n      "name": "svVchImportFormat",\n      "value": "jsonex"\n    },\n    {\n      "name": "svCurrentCompany",\n      "value": "Bhrama Enterprises"\n    }\n  ],\n  "tallymessage": [\n    {\n      "metadata": {\n        "type": "Voucher",\n        "vchtype": "Payment",\n        "action": "Create",\n        "objview": "Accounting Voucher View"\n      },\n      "date": "20250831",\n      "vouchertypename": "Payment",\n      "partyledgername": "Akshaya Enterprises",\n      "persistedview": "Accounting Voucher View",\n      "allledgerentries": [\n        {\n          "ledgername": "Akshaya Enterprises",\n          "isdeemedpositive": true,\n          "ispartyledger": true,\n          "amount": "-200.00",\n          "billallocations": [\n            {\n              "name": "16",\n              "billtype": "New Ref",\n              "amount": "-200.00"\n            }\n          ]\n        },\n        {\n          "ledgername": "Kotak Bank",\n          "isdeemedpositive": false,\n          "ispartyledger": true,\n          "amount": "200.00",\n          "bankallocations": [\n            {\n              "date": "20250831",\n              "instrumentdate": "20250831",\n              "email": "a@gmail.com",\n              "transactiontype": "Inter Bank Transfer",\n              "ifscode": "KKBK0000431",\n              "bankname": "Kotak Mahindra Bank (India)",\n              "accountnumber": "4891289138912",\n              "paymentfavouring": "Akshaya Enterprises",\n              "transactionname": "Primary",\n              "transfermode": "NEFT",\n              "bankid": "10",\n              "instrumentnumber": "100",\n              "paymentmode": "Transacted",\n              "bankpartyname": "Akshaya Enterprises",\n              "amount": "200.00"\n            }\n          ]\n        }\n      ]\n    }\n  ]\n}',

      XML: '<ENVELOPE>\n    <HEADER>\n        <VERSION>1</VERSION>\n        <TALLYREQUEST>Import</TALLYREQUEST>\n        <TYPE>Data</TYPE>\n        <ID>Vouchers</ID>\n    </HEADER>\n    <BODY>\n        <DESC>\n            <STATICVARIABLES>\n                <SVVCHIMPORTFORMAT>XML</SVVCHIMPORTFORMAT>\n                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>\n            </STATICVARIABLES>\n<TALLYMESSAGE>\n <VOUCHER VCHTYPE="Payment" ACTION="Create" OBJVIEW="Accounting Voucher View">\n  <DATE>20250831</DATE>\n  <VOUCHERTYPENAME>Payment</VOUCHERTYPENAME>\n  <PARTYLEDGERNAME>Akshaya Enterprises</PARTYLEDGERNAME>\n  <ALLLEDGERENTRIES.LIST>\n   <LEDGERNAME>Akshaya Enterprises</LEDGERNAME>\n   <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>\n   <ISPARTYLEDGER>Yes</ISPARTYLEDGER>\n   <AMOUNT>-200.00</AMOUNT>\n   <BILLALLOCATIONS.LIST>\n<NAME>29</NAME>\n<BILLTYPE>New Ref</BILLTYPE>\n<AMOUNT>-200.00</AMOUNT>\n   </BILLALLOCATIONS.LIST>\n  </ALLLEDGERENTRIES.LIST>\n  <ALLLEDGERENTRIES.LIST>\n   <LEDGERNAME>Kotak Bank</LEDGERNAME>\n   <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>\n   <ISPARTYLEDGER>Yes</ISPARTYLEDGER>\n   <AMOUNT>200.00</AMOUNT>\n   <BANKALLOCATIONS.LIST>\n<DATE>20250831</DATE>\n<INSTRUMENTDATE>20250831</INSTRUMENTDATE>\n<EMAIL>a@gmail.com</EMAIL>\n<TRANSACTIONTYPE>Inter Bank Transfer</TRANSACTIONTYPE>\n<IFSCODE>KKBK0000431</IFSCODE>\n<BANKNAME>Kotak Mahindra Bank (India)</BANKNAME>\n<ACCOUNTNUMBER>4891289138912</ACCOUNTNUMBER>\n<PAYMENTFAVOURING>Akshaya Enterprises</PAYMENTFAVOURING>\n<TRANSACTIONNAME>Primary</TRANSACTIONNAME>\n<TRANSFERMODE>NEFT</TRANSFERMODE>\n<INSTRUMENTNUMBER>6556876878</INSTRUMENTNUMBER>\n<PAYMENTMODE>Transacted</PAYMENTMODE>\n<BANKPARTYNAME>Akshaya Enterprises</BANKPARTYNAME>\n<AMOUNT>200.00</AMOUNT>\n   </BANKALLOCATIONS.LIST>\n  </ALLLEDGERENTRIES.LIST>\n </VOUCHER>\n</TALLYMESSAGE>\n</DESC>\n</BODY>\n</ENVELOPE>',
    },
    "payment-create-cash": {
      JSON: '{\n  "static_variables": [\n    {\n      "name": "svVchImportFormat",\n      "value": "jsonex"\n    },\n    {\n      "name": "svCurrentCompany",\n      "value": "Bhrama Enterprises"\n    }\n  ],\n  "tallymessage": [\n    {\n      "metadata": {\n        "type": "Voucher",\n        "vchtype": "Payment",\n        "action": "Create",\n        "objview": "Accounting Voucher View"\n      },\n      "date": "20250831",\n      "vouchertypename": "Payment",\n      "partyledgername": "Cash",\n      "persistedview": "Accounting Voucher View",\n      "allledgerentries": [\n        {\n          "ledgername": "Sundry Expenses",\n          "isdeemedpositive": true,\n          "ispartyledger": false,\n          "amount": "-100.00",\n          "categoryallocations": [\n            {\n              "category": "Primary Cost Category",\n              "isdeemedpositive": true,\n              "costcentreallocations": [\n                {\n                  "name": "CostName",\n                  "amount": "-100.00"\n                }\n              ]\n            }\n          ]\n        },\n        {\n          "ledgername": "Cash",\n          "isdeemedpositive": false,\n          "ispartyledger": true,\n          "amount": "100.00"\n        }\n      ]\n    }\n  ]\n}',

      XML: '<ENVELOPE>\n    <HEADER>\n        <VERSION>1</VERSION>\n        <TALLYREQUEST>Import</TALLYREQUEST>\n        <TYPE>Data</TYPE>\n        <ID>Vouchers</ID>\n    </HEADER>\n    <BODY>\n        <DESC>\n            <STATICVARIABLES>\n                <SVVCHIMPORTFORMAT>XML</SVVCHIMPORTFORMAT>\n                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>\n            </STATICVARIABLES>\n<TALLYMESSAGE xmlns:UDF="TallyUDF">\n <VOUCHER VCHTYPE="Payment" ACTION="Create" OBJVIEW="Accounting Voucher View">\n  <DATE>20250831</DATE>\n  <VOUCHERTYPENAME>Payment</VOUCHERTYPENAME>\n  <PARTYLEDGERNAME>Cash</PARTYLEDGERNAME>\n  <ALLLEDGERENTRIES.LIST>\n   <LEDGERNAME>Sundry Expenses</LEDGERNAME>\n   <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>\n   <ISPARTYLEDGER>No</ISPARTYLEDGER>\n   <AMOUNT>-100.00</AMOUNT>\n   <CATEGORYALLOCATIONS.LIST>\n<CATEGORY>Primary Cost Category</CATEGORY>\n<ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>\n<COSTCENTREALLOCATIONS.LIST>\n <NAME>CostName</NAME>\n <AMOUNT>-100.00</AMOUNT>\n</COSTCENTREALLOCATIONS.LIST>\n   </CATEGORYALLOCATIONS.LIST>\n  </ALLLEDGERENTRIES.LIST>\n  <ALLLEDGERENTRIES.LIST>\n   <LEDGERNAME>Cash</LEDGERNAME>\n   <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>\n   <ISPARTYLEDGER>Yes</ISPARTYLEDGER>\n   <AMOUNT>100.00</AMOUNT>\n  </ALLLEDGERENTRIES.LIST>\n </VOUCHER>\n</TALLYMESSAGE>\n</DESC>\n</BODY>\n</ENVELOPE>',
    },
    "payment-alter": {
      JSON: '{\n  "static_variables": [\n    {\n      "name": "svVchImportFormat",\n      "value": "jsonex"\n    },\n    {\n      "name": "svCurrentCompany",\n      "value": "Bhrama Enterprises"\n    }\n  ],\n  "tallymessage": [\n    {\n      "metadata": {\n        "type": "Voucher",\n        "remoteid": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000095",\n        "vchkey": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b348:00000058",\n        "vchtype": "Payment",\n        "action": "Alter",\n        "objview": "Accounting Voucher View"\n      },\n      "date": "20250801",\n      "guid": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000095"\n    }\n  ]\n}',

      XML: '<ENVELOPE>\n    <HEADER>\n        <VERSION>1</VERSION>\n        <TALLYREQUEST>Import</TALLYREQUEST>\n        <TYPE>Data</TYPE>\n        <ID>Vouchers</ID>\n    </HEADER>\n    <BODY>\n        <DESC>\n            <STATICVARIABLES>\n                <SVVCHIMPORTFORMAT>XML</SVVCHIMPORTFORMAT>\n                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>\n            </STATICVARIABLES>\n<TALLYMESSAGE xmlns:UDF="TallyUDF">\n      <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000095" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b348:00000058" VCHTYPE="Payment" ACTION="Alter" OBJVIEW="Accounting Voucher View">\n  <DATE>20250801</DATE>\n  <GUID>f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000095</GUID>\n </VOUCHER>\n</TALLYMESSAGE>\n</DESC>\n</BODY>\n</ENVELOPE>',
    },
    "payment-delete": {
      JSON: '{\n  "static_variables": [\n    {\n      "name": "svVchImportFormat",\n      "value": "jsonex"\n    },\n    {\n      "name": "svCurrentCompany",\n      "value": "Bhrama Enterprises"\n    }\n  ],\n  "tallymessage": [\n    {\n      "metadata": {\n        "type": "Voucher",\n        "remoteid": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000095",\n        "vchkey": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b348:00000058",\n        "vchtype": "Payment",\n        "action": "Delete",\n        "objview": "Accounting Voucher View"\n      },\n      "guid": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000095"\n    }\n  ]\n}',

      XML: '<ENVELOPE>\n    <HEADER>\n        <VERSION>1</VERSION>\n        <TALLYREQUEST>Import</TALLYREQUEST>\n        <TYPE>Data</TYPE>\n        <ID>Vouchers</ID>\n    </HEADER>\n    <BODY>\n        <DESC>\n            <STATICVARIABLES>\n                <SVVCHIMPORTFORMAT>XML</SVVCHIMPORTFORMAT>\n                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>\n            </STATICVARIABLES>\n<TALLYMESSAGE xmlns:UDF="TallyUDF">\n <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000095" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b348:00000058" VCHTYPE="Payment" ACTION="Delete" OBJVIEW="Accounting Voucher View">\n  <GUID>f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000095</GUID>\n </VOUCHER>\n</TALLYMESSAGE>\n</DESC>\n</BODY>\n</ENVELOPE>',
    },
    "payment-pull-all": {
      JSON: '{\n  "static_variables": [\n    {\n      "name": "svExportFormat",\n      "value": "jsonex"\n    },\n    {\n      "name": "svCurrentCompany",\n      "value": "Bhrama Enterprises"\n    }\n  ],\n  "tdlmessage": [\n    {\n      "definitions": [\n        {\n          "metadata": {\n            "name": "TSPL All Payment Vouchers",\n            "type": "Collection"\n          },\n          "attributes": [\n            {\n              "Type": "Vouchers:VoucherType"\n            },\n            {\n              "Child Of": "$$VchTypePayment"\n            },\n            {\n              "Native Method": "Date, VoucherTypeName, VoucherNumber, partyledgername"\n            }\n          ]\n        }\n      ]\n    }\n  ]\n}',

      XML: '<ENVELOPE>\n    <HEADER>\n        <VERSION>1</VERSION>\n        <TALLYREQUEST>Export</TALLYREQUEST>\n        <TYPE>Collection</TYPE>\n        <ID>TSPL All Payment Vouchers</ID>\n    </HEADER>\n    <BODY>\n        <DESC>\n            <STATICVARIABLES>\n                <SVEXPORTFORMAT>XML</SVEXPORTFORMAT>\n                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>\n            </STATICVARIABLES>\n           <TDL>\n   <TDLMESSAGE>\n  <COLLECTION NAME="TSPL All Payment Vouchers" ISMODIFY="No" ISFIXED="No" ISINITIALIZE="No" ISOPTION="No" ISINTERNAL="No">\n   <TYPE>Vouchers:VoucherType</TYPE>\n   <CHILDOF>$$VchTypePayment</CHILDOF>\n   <NATIVEMETHOD>Date, VoucherTypeName, VoucherNumber, Partyledgername</NATIVEMETHOD>\n   <NATIVEMETHOD>AllLedgerEntries.BankAllocations.*</NATIVEMETHOD>\n  </COLLECTION>\n</TDLMESSAGE>\n</TDL>\n        </DESC>\n    </BODY>\n</ENVELOPE>',
    },
    "payment-pull-period": {
      JSON: '{\n  "static_variables": [\n    {\n      "name": "svExportFormat",\n      "value": "jsonex"\n    },\n    {\n      "name": "svCurrentCompany",\n      "value": "Bhrama Enterprises"\n    }\n  ],\n  "tdlmessage": [\n    {\n      "definitions": [\n        {\n          "metadata": {\n            "name": "TSPL Payment Vouchers",\n            "type": "Collection"\n          },\n          "attributes": [\n            {\n              "Type": "Vouchers:VoucherType"\n            },\n            {\n              "Child Of": "$$VchTypePayment"\n            },\n            {\n              "Native Method": "Date, VoucherTypeName, VoucherNumber, partyledgername"\n            },\n            {\n              "Filters": "Period Filter"\n            }\n          ]\n        },\n        {\n          "metadata": {\n            "name": "PeriodFilter",\n            "type": "System",\n            "sys_type": "Formulae",\n            "ismodify": true\n          },\n          "value": "$Date >= $$Date:\\"1-Apr-2025\\" AND $Date <= $$Date:\\"10-Apr-2025\\"" \n        }\n      ]\n    }\n  ]\n}',

      XML: '<ENVELOPE>\n    <HEADER>\n        <VERSION>1</VERSION>\n        <TALLYREQUEST>Export</TALLYREQUEST>\n        <TYPE>Collection</TYPE>\n        <ID>TSPL Payment Vouchers</ID>\n    </HEADER>\n    <BODY>\n        <DESC>\n            <STATICVARIABLES>\n                <SVEXPORTFORMAT>XML</SVEXPORTFORMAT>\n                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>\n            </STATICVARIABLES>\n           <TDL>\n   <TDLMESSAGE>\n  <COLLECTION NAME="TSPL Payment Vouchers" ISMODIFY="No" ISFIXED="No" ISINITIALIZE="No" ISOPTION="No" ISINTERNAL="No">\n   <TYPE>Vouchers:VoucherType</TYPE>\n   <CHILDOF>$$VchTypePayment</CHILDOF>\n   <NATIVEMETHOD>Date, VoucherTypeName, VoucherNumber, Partyledgername</NATIVEMETHOD>\n   <NATIVEMETHOD>AllLedgerEntries.BankAllocations.*</NATIVEMETHOD>\n   <FILTERS>Period Filter</FILTERS>\n  </COLLECTION>\n  <SYSTEM TYPE="Formulae" NAME="PeriodFilter" ISMODIFY="Yes" ISFIXED="No" ISINTERNAL="No">$Date &gt;= ($$Date:&quot;01-04-2025&quot;) AND $Date &lt;= ($$Date:&quot;10-04-2025&quot;)  </SYSTEM>\n</TDLMESSAGE>\n</TDL>\n        </DESC>\n    </BODY>\n</ENVELOPE>',
    },
    /* Receipt */
    "receipt-create": {
      JSON: '{\n  "static_variables": [\n    {\n      "name": "svVchImportFormat",\n      "value": "jsonex"\n    },\n    {\n      "name": "svCurrentCompany",\n      "value": "Bhrama Enterprises"\n    }\n  ],\n  "tallymessage": [\n    {\n      "metadata": {\n        "type": "Voucher",\n        "vchtype": "Receipt",\n        "action": "Create",\n        "objview": "Accounting Voucher View"\n      },\n      "date": "20250831",\n      "vouchertypename": "Receipt",\n      "partyledgername": "ABC Party",\n      "allledgerentries": [\n        {\n          "ledgername": "ABC Party",\n          "isdeemedpositive": false,\n          "ispartyledger": true,\n          "amount": "2500.00"\n        },\n        {\n          "ledgername": "Kotak Bank",\n          "isdeemedpositive": true,\n          "ispartyledger": true,\n          "amount": "-2500.00",\n          "bankallocations": [\n            {\n              "date": "20250831",\n              "instrumentdate": "20250831",\n              "transactiontype": "Cheque/DD",\n              "bankname": "Kotak Mahindra Bank (India)",\n              "paymentfavouring": "ABC Party",\n              "instrumentnumber": "56465787",\n              "paymentmode": "Transacted",\n              "bankpartyname": "ABC Party",\n              "amount": "-2500.00"\n            }\n          ]\n        }\n      ]\n    }\n  ]\n}',

      XML: '<ENVELOPE>\n    <HEADER>\n        <VERSION>1</VERSION>\n        <TALLYREQUEST>Import</TALLYREQUEST>\n        <TYPE>Data</TYPE>\n        <ID>Vouchers</ID>\n    </HEADER>\n    <BODY>\n        <DESC>\n            <STATICVARIABLES>\n                <SVVCHIMPORTFORMAT>XML</SVVCHIMPORTFORMAT>\n                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>\n            </STATICVARIABLES>\n<TALLYMESSAGE xmlns:UDF="TallyUDF">\n <VOUCHER VCHTYPE="Receipt" ACTION="Create" OBJVIEW="Accounting Voucher View">\n  <DATE>20250831</DATE>\n  <VOUCHERTYPENAME>Receipt</VOUCHERTYPENAME>\n  <PARTYLEDGERNAME>ABC Party</PARTYLEDGERNAME>\n  <ALLLEDGERENTRIES.LIST>\n   <LEDGERNAME>ABC Party</LEDGERNAME>\n   <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>\n   <ISPARTYLEDGER>Yes</ISPARTYLEDGER>\n   <AMOUNT>2500.00</AMOUNT>\n  </ALLLEDGERENTRIES.LIST>\n  <ALLLEDGERENTRIES.LIST>\n   <LEDGERNAME>Kotak Bank</LEDGERNAME>\n   <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>\n   <ISPARTYLEDGER>Yes</ISPARTYLEDGER>\n   <AMOUNT>-2500.00</AMOUNT>\n   <BANKALLOCATIONS.LIST>\n<DATE>20250831</DATE>\n<INSTRUMENTDATE>20250831</INSTRUMENTDATE>\n<TRANSACTIONTYPE>Cheque/DD</TRANSACTIONTYPE>\n<BANKNAME>Kotak Mahindra Bank (India)</BANKNAME>\n<PAYMENTFAVOURING>ABC Party</PAYMENTFAVOURING>\n<INSTRUMENTNUMBER>56465787</INSTRUMENTNUMBER>\n<PAYMENTMODE>Transacted</PAYMENTMODE>\n<BANKPARTYNAME>ABC Party</BANKPARTYNAME>\n<ISCONNECTEDPAYMENT>No</ISCONNECTEDPAYMENT>\n<AMOUNT>-2500.00</AMOUNT>\n   </BANKALLOCATIONS.LIST>\n  </ALLLEDGERENTRIES.LIST>\n </VOUCHER>\n</TALLYMESSAGE>\n</DESC>\n</BODY>\n</ENVELOPE>',
    },
    "receipt-create-cash": {
      JSON: '{\n  "static_variables": [\n    {\n      "name": "svVchImportFormat",\n      "value": "jsonex"\n    },\n    {\n      "name": "svCurrentCompany",\n      "value": "Bhrama Enterprises"\n    }\n  ],\n  "tallymessage": [\n    {\n      "metadata": {\n        "type": "Voucher",\n        "vchtype": "Receipt",\n        "action": "Create",\n        "objview": "Accounting Voucher View"\n      },\n      "date": "20250831",\n      "vouchertypename": "Receipt",\n      "partyname": "Cash",\n      "partyledgername": "Cash",\n      "allledgerentries": [\n        {\n          "ledgername": "Income",\n          "isdeemedpositive": false,\n          "ispartyledger": false,\n          "amount": "100.00",\n          "categoryallocations": [\n            {\n              "category": "Primary Cost Category",\n              "isdeemedpositive": false,\n              "costcentreallocations": [\n                {\n                  "name": "CostName",\n                  "amount": "100.00"\n                }\n              ]\n            }\n          ]\n        },\n        {\n          "ledgername": "Cash",\n          "isdeemedpositive": true,\n          "ispartyledger": true,\n          "amount": "-100.00"\n        }\n      ]\n    }\n  ]\n}',

      XML: '<ENVELOPE>\n    <HEADER>\n        <VERSION>1</VERSION>\n        <TALLYREQUEST>Import</TALLYREQUEST>\n        <TYPE>Data</TYPE>\n        <ID>Vouchers</ID>\n    </HEADER>\n    <BODY>\n        <DESC>\n            <STATICVARIABLES>\n                <SVVCHIMPORTFORMAT>XML</SVVCHIMPORTFORMAT>\n                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>\n            </STATICVARIABLES>\n<TALLYMESSAGE xmlns:UDF="TallyUDF">\n <VOUCHER VCHTYPE="Receipt" ACTION="Create" OBJVIEW="Accounting Voucher View">\n  <DATE>20250831</DATE>\n  <VOUCHERTYPENAME>Receipt</VOUCHERTYPENAME>\n  <PARTYNAME>Cash</PARTYNAME>\n  <PARTYLEDGERNAME>Cash</PARTYLEDGERNAME>\n  <ALLLEDGERENTRIES.LIST>\n   <LEDGERNAME>Income</LEDGERNAME>\n   <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>\n   <ISPARTYLEDGER>No</ISPARTYLEDGER>\n   <AMOUNT>100.00</AMOUNT>\n   <CATEGORYALLOCATIONS.LIST>\n<CATEGORY>Primary Cost Category</CATEGORY>\n<ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>\n<COSTCENTREALLOCATIONS.LIST>\n <NAME>CostName</NAME>\n <AMOUNT>100.00</AMOUNT>\n</COSTCENTREALLOCATIONS.LIST>\n   </CATEGORYALLOCATIONS.LIST>\n  </ALLLEDGERENTRIES.LIST>\n  <ALLLEDGERENTRIES.LIST>\n   <LEDGERNAME>Cash</LEDGERNAME>\n   <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>\n   <ISPARTYLEDGER>Yes</ISPARTYLEDGER>\n   <AMOUNT>-100.00</AMOUNT>\n  </ALLLEDGERENTRIES.LIST>\n </VOUCHER>\n</TALLYMESSAGE>\n</DESC>\n</BODY>\n</ENVELOPE>',
    },
    "receipt-alter": {
      JSON: '{\n  "static_variables": [\n    {\n      "name": "svVchImportFormat",\n      "value": "jsonex"\n    },\n    {\n      "name": "svCurrentCompany",\n      "value": "Bhrama Enterprises"\n    }\n  ],\n  "tallymessage": [\n    {\n      "metadata": {\n        "type": "Voucher",\n        "vchtype": "Receipt",\n        "remoteid": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000006d",\n        "vchkey": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b34b:000000d0",\n        "action": "Alter",\n        "objview": "Accounting Voucher View"\n      },\n      "date": "20250801",\n      "guid": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000006d"\n    }\n  ]\n}',

      XML: '<ENVELOPE>\n    <HEADER>\n        <VERSION>1</VERSION>\n        <TALLYREQUEST>Import</TALLYREQUEST>\n        <TYPE>Data</TYPE>\n        <ID>Vouchers</ID>\n    </HEADER>\n    <BODY>\n        <DESC>\n            <STATICVARIABLES>\n                <SVVCHIMPORTFORMAT>XML</SVVCHIMPORTFORMAT>\n                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>\n            </STATICVARIABLES>\n<TALLYMESSAGE xmlns:UDF="TallyUDF">\n <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000006b" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b34b:000000d0" VCHTYPE="Receipt" ACTION="Alter" OBJVIEW="Accounting Voucher View">\n  <DATE>20250801</DATE>\n  <GUID>f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000006b</GUID>\n </VOUCHER>\n</TALLYMESSAGE>\n</DESC>\n</BODY>\n</ENVELOPE>',
    },
    "receipt-delete": {
      JSON: '{\n  "static_variables": [\n    {\n      "name": "svVchImportFormat",\n      "value": "jsonex"\n    },\n    {\n      "name": "svCurrentCompany",\n      "value": "Bhrama Enterprises"\n    }\n  ],\n  "tallymessage": [\n    {\n      "metadata": {\n        "type": "Voucher",\n        "vchtype": "Receipt",\n        "remoteid": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000006d",\n        "vchkey": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b34b:000000d0",\n        "action": "Delete",\n        "objview": "Accounting Voucher View"\n      },\n      "guid": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000006d"\n    }\n  ]\n}',

      XML: '<ENVELOPE>\n    <HEADER>\n        <VERSION>1</VERSION>\n        <TALLYREQUEST>Import</TALLYREQUEST>\n        <TYPE>Data</TYPE>\n        <ID>Vouchers</ID>\n    </HEADER>\n    <BODY>\n        <DESC>\n            <STATICVARIABLES>\n                <SVVCHIMPORTFORMAT>XML</SVVCHIMPORTFORMAT>\n                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>\n            </STATICVARIABLES>\n<TALLYMESSAGE xmlns:UDF="TallyUDF">\n <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000006b" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b34b:000000d0" VCHTYPE="Receipt" ACTION="Delete" OBJVIEW="Accounting Voucher View">\n  <GUID>f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000006b</GUID>\n </VOUCHER>\n</TALLYMESSAGE>\n</DESC>\n</BODY>\n</ENVELOPE>',
    },
    "receipt-pull-all": {
      JSON: '{\n  "static_variables": [\n    {\n      "name": "svExportFormat",\n      "value": "jsonex"\n    },\n    {\n      "name": "svCurrentCompany",\n      "value": "Bhrama Enterprises"\n    }\n  ],\n  "tdlmessage": [\n    {\n      "definitions": [\n        {\n          "metadata": {\n            "name": "TSPL All Receipt Vouchers",\n            "type": "Collection"\n          },\n          "attributes": [\n            {\n              "Type": "Vouchers:VoucherType"\n            },\n            {\n              "Child Of": "$$VchTypeReceipt"\n            },\n            {\n              "Native Method": "Date, VoucherTypeName, VoucherNumber, Partyledgername"\n            }\n          ]\n        }\n      ]\n    }\n  ]\n}',

      XML: '<ENVELOPE>\n    <HEADER>\n        <VERSION>1</VERSION>\n        <TALLYREQUEST>Export</TALLYREQUEST>\n        <TYPE>Collection</TYPE>\n        <ID>TSPL All Receipt Vouchers</ID>\n    </HEADER>\n    <BODY>\n        <DESC>\n            <STATICVARIABLES>\n                <SVEXPORTFORMAT>XML</SVEXPORTFORMAT>\n                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>\n            </STATICVARIABLES>\n<TDL>\n<TDLMESSAGE>\n  <COLLECTION NAME="TSPL All Receipt Vouchers" ISMODIFY="No" ISFIXED="No" ISINITIALIZE="No" ISOPTION="No" ISINTERNAL="No">\n   <TYPE>Vouchers:VoucherType</TYPE>\n   <CHILDOF>$$VchTypeReceipt</CHILDOF>\n   <NATIVEMETHOD>Date, VoucherTypeName, VoucherNumber, Partyledgername</NATIVEMETHOD>\n  </COLLECTION>\n</TDLMESSAGE>\n</TDL>\n        </DESC>\n    </BODY>\n</ENVELOPE>',
    },
    "receipt-pull-period": {
      JSON: '{\n  "static_variables": [\n    {\n      "name": "svExportFormat",\n      "value": "jsonex"\n    },\n    {\n      "name": "svCurrentCompany",\n      "value": "Bhrama Enterprises"\n    }\n  ],\n  "tdlmessage": [\n    {\n      "definitions": [\n        {\n          "metadata": {\n            "name": "TSPL Receipt Vouchers",\n            "type": "Collection"\n          },\n          "attributes": [\n            {\n              "Type": "Vouchers:VoucherType"\n            },\n            {\n              "Child Of": "$$VchTypeReceipt"\n            },\n            {\n              "Native Method": "Date, VoucherTypeName, VoucherNumber, Partyledgername"\n            },\n            {\n              "Filters": "Period Filter"\n            }\n          ]\n        },\n        {\n          "metadata": {\n            "name": "PeriodFilter",\n            "type": "System",\n            "sys_type": "Formulae",\n            "ismodify": true\n          },\n          "value": "$Date >= ($$Date:\\"01-07-2025\\") AND $Date <= ($$Date:\\"10-07-2025\\")"\n        }\n      ]\n    }\n  ]\n}',

      XML: '<ENVELOPE>\n    <HEADER>\n        <VERSION>1</VERSION>\n        <TALLYREQUEST>Export</TALLYREQUEST>\n        <TYPE>Collection</TYPE>\n        <ID>TSPL Receipt Vouchers</ID>\n    </HEADER>\n    <BODY>\n        <DESC>\n            <STATICVARIABLES>\n                <SVEXPORTFORMAT>XML</SVEXPORTFORMAT>\n                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>\n            </STATICVARIABLES>\n<TDL>\n<TDLMESSAGE>\n  <COLLECTION NAME="TSPL Receipt Vouchers" ISMODIFY="No" ISFIXED="No" ISINITIALIZE="No" ISOPTION="No" ISINTERNAL="No">\n   <TYPE>Vouchers:VoucherType</TYPE>\n   <CHILDOF>$$VchTypeReceipt</CHILDOF>\n   <NATIVEMETHOD>Date, VoucherTypeName, VoucherNumber, Partyledgername</NATIVEMETHOD>\n   <FILTERS>Period Filter</FILTERS>\n  </COLLECTION>\n  <SYSTEM TYPE="Formulae" NAME="PeriodFilter" ISMODIFY="Yes" ISFIXED="No" ISINTERNAL="No">$Date &gt;= ($$Date:&quot;01-07-2025&quot;) AND $Date &lt;= ($$Date:&quot;10-07-2025&quot;)  </SYSTEM>\n</TDLMESSAGE>\n</TDL>\n        </DESC>\n    </BODY>\n</ENVELOPE>',
    },
    /* Sales */
    "sales-create-item": {
      JSON: '{\n  "static_variables": [\n    {\n      "name": "svVchImportFormat",\n      "value": "jsonex"\n    },\n    {\n      "name": "svCurrentCompany",\n      "value": "Bhrama Enterprises"\n    }\n  ],\n  "tallymessage": [\n    {\n      "metadata": {\n        "type": "Voucher",\n        "vchtype": "Sales",\n        "action": "Create",\n        "objview": "Invoice Voucher View"\n      },\n      "date": "20250831",\n      "vouchertypename": "Sales",\n      "partyname": "Amar Enterprises",\n      "partyledgername": "Amar Enterprises",\n      "allinventoryentries": [\n        {\n          "stockitemname": "Coffee Powder",\n          "isdeemedpositive": false,\n          "rate": "2.00/nos",\n          "amount": "40.00",\n          "actualqty": " 20 nos",\n          "billedqty": " 20 nos",\n          "batchallocations": [\n            {\n              "godownname": "Main Location",\n              "batchname": "Primary Batch",\n              "destinationgodownname": "Main Location",\n              "trackingnumber": "T001",\n              "amount": "40.00",\n              "actualqty": " 20 nos",\n              "billedqty": " 20 nos"\n            }\n          ],\n          "accountingallocations": [\n            {\n              "oldauditentryids": [\n                {\n                  "metadata": true,\n                  "type": "Number"\n                },\n                "-1"\n              ],\n              "ledgername": "Sales",\n              "isdeemedpositive": false,\n              "ispartyledger": false,\n              "amount": "40.00"\n            }\n          ]\n        }\n      ],\n      "ledgerentries": [\n        {\n          "oldauditentryids": [\n            {\n              "metadata": true,\n              "type": "Number"\n            },\n            "-1"\n          ],\n          "ledgername": "Amar Enterprises",\n          "isdeemedpositive": true,\n          "ispartyledger": true,\n          "amount": "-40.00",\n          "billallocations": [\n            {\n              "name": "12",\n              "billtype": "New Ref",\n              "amount": "-40.00"\n            }\n          ]\n        }\n      ]\n    }\n  ]\n}',

      XML: '<ENVELOPE>\n    <HEADER>\n        <VERSION>1</VERSION>\n        <TALLYREQUEST>Import</TALLYREQUEST>\n        <TYPE>Data</TYPE>\n        <ID>Vouchers</ID>\n    </HEADER>\n    <BODY>\n        <DESC>\n            <STATICVARIABLES>\n                <SVVCHIMPORTFORMAT>XML</SVVCHIMPORTFORMAT>\n                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>\n            </STATICVARIABLES>\n<TALLYMESSAGE xmlns:UDF="TallyUDF">\n <VOUCHER VCHTYPE="Sales" ACTION="Create" OBJVIEW="Accounting Voucher View">\n  <DATE>20250831</DATE>\n  <VOUCHERTYPENAME>Sales</VOUCHERTYPENAME>\n  <PARTYNAME>Amar Enterprises</PARTYNAME>\n  <PARTYLEDGERNAME>Amar Enterprises</PARTYLEDGERNAME>\n  <PERSISTEDVIEW>Invoice Voucher View</PERSISTEDVIEW>\n  <ALLLEDGERENTRIES.LIST>\n   <OLDAUDITENTRYIDS.LIST TYPE="Number">\n<OLDAUDITENTRYIDS>-1</OLDAUDITENTRYIDS>\n   </OLDAUDITENTRYIDS.LIST>\n   <LEDGERNAME>Amar Enterprises</LEDGERNAME>\n   <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>\n   <ISPARTYLEDGER>Yes</ISPARTYLEDGER>\n   <AMOUNT>-40.00</AMOUNT>\n   <BILLALLOCATIONS.LIST>\n<NAME>12</NAME>\n<BILLTYPE>New Ref</BILLTYPE>\n<AMOUNT>-40.00</AMOUNT>\n   </BILLALLOCATIONS.LIST>\n  </ALLLEDGERENTRIES.LIST>\n  <ALLLEDGERENTRIES.LIST>\n   <OLDAUDITENTRYIDS.LIST TYPE="Number">\n<OLDAUDITENTRYIDS>-1</OLDAUDITENTRYIDS>\n   </OLDAUDITENTRYIDS.LIST>\n   <LEDGERNAME>Sales</LEDGERNAME>\n   <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>\n   <ISPARTYLEDGER>No</ISPARTYLEDGER>\n   <AMOUNT>40.00</AMOUNT>\n   <INVENTORYALLOCATIONS.LIST>\n<STOCKITEMNAME>Coffee Powder</STOCKITEMNAME>\n<ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>\n<RATE>2.00/nos</RATE>\n<AMOUNT>40.00</AMOUNT>\n<ACTUALQTY> 20 nos</ACTUALQTY>\n<BILLEDQTY> 20 nos</BILLEDQTY>\n<BATCHALLOCATIONS.LIST>\n <GODOWNNAME>Main Location</GODOWNNAME>\n <BATCHNAME>Primary Batch</BATCHNAME>\n <DESTINATIONGODOWNNAME>Main Location</DESTINATIONGODOWNNAME>\n <TRACKINGNUMBER>T001</TRACKINGNUMBER>\n <AMOUNT>40.00</AMOUNT>\n <ACTUALQTY> 20 nos</ACTUALQTY>\n <BILLEDQTY> 20 nos</BILLEDQTY>\n</BATCHALLOCATIONS.LIST>\n   </INVENTORYALLOCATIONS.LIST>\n   </ALLLEDGERENTRIES.LIST>\n </VOUCHER>\n</TALLYMESSAGE>\n</DESC>\n</BODY>\n</ENVELOPE>',
    },
    "sales-create-gst": {
      JSON: '{\n  "static_variables": [\n    {\n      "name": "svVchImportFormat",\n      "value": "jsonex"\n    },\n    {\n      "name": "svCurrentCompany",\n      "value": "Bhrama Enterprises"\n    }\n  ],\n  "tallymessage": [\n    {\n      "metadata": {\n        "type": "Voucher",\n        "vchtype": "Sales",\n        "action": "Create",\n        "objview": "Invoice Voucher View"\n      },\n      "date": "20260301",\n      "vchstatusdate": "20260301",\n      "gstregistrationtype": "Regular",\n      "statename": "Karnataka",\n      "countryofresidence": "India",\n      "partygstin": "29AAACH1004N1ZQ",\n      "placeofsupply": "Karnataka",\n      "vouchertypename": "Sales",\n      "partyname": "Chanda Enterprises",\n      "gstregistration": {\n        "value": "Karnataka Registration",\n        "taxtype": "GST",\n        "taxregistration": "29AAECP4424C1ZN"\n      },\n      "cmpgstin": "29AAECP4424C1ZN",\n      "partyledgername": "Chanda Enterprises",\n      "basicbuyername": "Chanda Enterprises",\n      "cmpgstregistrationtype": "Regular",\n      "partymailingname": "Chanda Enterprises",\n      "dispatchfromname": "Bhrama Enterprises",\n      "dispatchfromstatename": "Karnataka",\n      "consigneegstin": "29AAACH1004N1ZQ",\n      "consigneemailingname": "Chanda Enterprises",\n      "consigneestatename": "Karnataka",\n      "cmpgststate": "Karnataka",\n      "consigneecountryname": "India",\n      "basicbasepartyname": "Chanda Enterprises",\n      "effectivedate": "20260301",\n      "isinvoice": true,\n      "allinventoryentries": [\n        {\n          "stockitemname": "GST Coffee",\n          "gstovrdnisrevchargeappl": "\\u0004 Not Applicable",\n          "gstovrdntaxability": "Taxable",\n          "gstsourcetype": "Stock Item",\n          "gstitemsource": "GST Coffee",\n          "hsnsourcetype": "Stock Item",\n          "hsnitemsource": "GST Coffee",\n          "gstovrdntypeofsupply": "Goods",\n          "gstrateinferapplicability": "As per Masters/Company",\n          "gsthsnname": "4820",\n          "gsthsninferapplicability": "As per Masters/Company",\n          "isdeemedpositive": false,\n          "rate": "75.00/nos",\n          "amount": "1500.00",\n          "actualqty": " 20 nos",\n          "billedqty": " 20 nos",\n          "batchallocations": [\n            {\n              "godownname": "Main Location",\n              "batchname": "Primary Batch",\n              "amount": "1500.00",\n              "actualqty": " 20 nos",\n              "billedqty": " 20 nos"\n            }\n          ],\n          "accountingallocations": [\n            {\n              "ledgername": "GST Sales",\n              "isdeemedpositive": false,\n              "ispartyledger": false,\n              "amount": "1500.00"\n            }\n          ],\n          "ratedetails": [\n            {\n              "gstratedutyhead": "CGST",\n              "gstratevaluationtype": "Based on Value",\n              "gstrate": " 2.50"\n            },\n            {\n              "gstratedutyhead": "SGST/UTGST",\n              "gstratevaluationtype": "Based on Value",\n              "gstrate": " 2.50"\n            },\n            {\n              "gstratedutyhead": "IGST",\n              "gstratevaluationtype": "Based on Value",\n              "gstrate": " 5"\n            },\n            {\n              "gstratedutyhead": "Cess",\n              "gstratevaluationtype": "\\u0004 Not Applicable"\n            },\n            {\n              "gstratedutyhead": "State Cess",\n              "gstratevaluationtype": "Based on Value"\n            }\n          ]\n        }\n      ],\n      "ledgerentries": [\n        {\n          "ledgername": "Chanda Enterprises",\n          "isdeemedpositive": true,\n          "ispartyledger": true,\n          "amount": "-1575.00",\n          "billallocations": [\n            {\n              "name": "22",\n              "billtype": "New Ref",\n              "tdsdeducteeisspecialrate": false,\n              "amount": "-1575.00"\n            }\n          ]\n        },\n        {\n          "ledgername": "CGST",\n          "isdeemedpositive": false,\n          "ispartyledger": false,\n          "amount": "37.50"\n        },\n        {\n          "ledgername": "SGST",\n          "isdeemedpositive": false,\n          "ispartyledger": false,\n          "amount": "37.50"\n        }\n      ]\n    }\n  ]\n}',

      XML: '<ENVELOPE>\n    <HEADER>\n        <VERSION>1</VERSION>\n        <TALLYREQUEST>Import</TALLYREQUEST>\n        <TYPE>Data</TYPE>\n        <ID>Vouchers</ID>\n    </HEADER>\n    <BODY>\n        <DESC>\n            <STATICVARIABLES>\n                <SVVCHIMPORTFORMAT>XML</SVVCHIMPORTFORMAT>\n                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>\n            </STATICVARIABLES>\n<TALLYMESSAGE xmlns:UDF="TallyUDF">\n<VOUCHER VCHTYPE="Sales" ACTION="Create" OBJVIEW="Invoice Voucher View">\n      <DATE>20260301</DATE>\n      <VCHSTATUSDATE>20260301</VCHSTATUSDATE>\n      <GSTREGISTRATIONTYPE>Regular</GSTREGISTRATIONTYPE>\n      <STATENAME>Karnataka</STATENAME>\n      <COUNTRYOFRESIDENCE>India</COUNTRYOFRESIDENCE>\n      <PARTYGSTIN>29AAACH1004N1ZQ</PARTYGSTIN>\n      <PLACEOFSUPPLY>Karnataka</PLACEOFSUPPLY>\n      <VOUCHERTYPENAME>Sales</VOUCHERTYPENAME>\n      <PARTYNAME>Chanda Enterprises</PARTYNAME>\n      <GSTREGISTRATION TAXTYPE="GST" TAXREGISTRATION="29AAECP4424C1ZN">Karnataka Registration</GSTREGISTRATION>\n      <CMPGSTIN>29AAECP4424C1ZN</CMPGSTIN>\n      <PARTYLEDGERNAME>Chanda Enterprises</PARTYLEDGERNAME>\n      <BASICBUYERNAME>Chanda Enterprises</BASICBUYERNAME>\n      <CMPGSTREGISTRATIONTYPE>Regular</CMPGSTREGISTRATIONTYPE>\n      <PARTYMAILINGNAME>Chanda Enterprises</PARTYMAILINGNAME>\n      <DISPATCHFROMNAME>Bhrama Enterprises</DISPATCHFROMNAME>\n      <DISPATCHFROMSTATENAME>Karnataka</DISPATCHFROMSTATENAME>\n      <CONSIGNEEGSTIN>29AAACH1004N1ZQ</CONSIGNEEGSTIN>\n      <CONSIGNEEMAILINGNAME>Chanda Enterprises</CONSIGNEEMAILINGNAME>\n      <CONSIGNEESTATENAME>Karnataka</CONSIGNEESTATENAME>\n      <CMPGSTSTATE>Karnataka</CMPGSTSTATE>\n      <CONSIGNEECOUNTRYNAME>India</CONSIGNEECOUNTRYNAME>\n      <BASICBASEPARTYNAME>Chanda Enterprises</BASICBASEPARTYNAME>\n      <EFFECTIVEDATE> 20260301 </EFFECTIVEDATE>\n      <ISINVOICE>Yes</ISINVOICE>\n      <ALLINVENTORYENTRIES.LIST>\n       <STOCKITEMNAME>GST Coffee</STOCKITEMNAME>\n       <GSTOVRDNISREVCHARGEAPPL>&#4; Not Applicable</GSTOVRDNISREVCHARGEAPPL>\n       <GSTOVRDNTAXABILITY>Taxable</GSTOVRDNTAXABILITY>\n       <GSTSOURCETYPE>Stock Item</GSTSOURCETYPE>\n       <GSTITEMSOURCE>GST Coffee</GSTITEMSOURCE>\n       <HSNSOURCETYPE>Stock Item</HSNSOURCETYPE>\n       <HSNITEMSOURCE>GST Coffee</HSNITEMSOURCE>\n       <GSTOVRDNTYPEOFSUPPLY>Goods</GSTOVRDNTYPEOFSUPPLY>\n       <GSTRATEINFERAPPLICABILITY>As per Masters/Company</GSTRATEINFERAPPLICABILITY>\n       <GSTHSNNAME>4820</GSTHSNNAME>\n       <GSTHSNINFERAPPLICABILITY>As per Masters/Company</GSTHSNINFERAPPLICABILITY>\n       <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>\n       <RATE>75.00/nos</RATE>\n       <AMOUNT>1500.00</AMOUNT>\n       <ACTUALQTY> 20 nos</ACTUALQTY>\n       <BILLEDQTY> 20 nos</BILLEDQTY>\n       <BATCHALLOCATIONS.LIST>\n        <GODOWNNAME>Main Location</GODOWNNAME>\n        <BATCHNAME>Primary Batch</BATCHNAME>\n        <AMOUNT>1500.00</AMOUNT>\n        <ACTUALQTY> 20 nos</ACTUALQTY>\n        <BILLEDQTY> 20 nos</BILLEDQTY>\n       </BATCHALLOCATIONS.LIST>\n       <ACCOUNTINGALLOCATIONS.LIST>\n        <LEDGERNAME>GST Sales</LEDGERNAME>\n        <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>\n        <ISPARTYLEDGER>No</ISPARTYLEDGER>\n        <AMOUNT>1500.00</AMOUNT>\n       </ACCOUNTINGALLOCATIONS.LIST>\n       <RATEDETAILS.LIST>\n        <GSTRATEDUTYHEAD>CGST</GSTRATEDUTYHEAD>\n        <GSTRATEVALUATIONTYPE>Based on Value</GSTRATEVALUATIONTYPE>\n        <GSTRATE> 2.50</GSTRATE>\n       </RATEDETAILS.LIST>\n       <RATEDETAILS.LIST>\n        <GSTRATEDUTYHEAD>SGST/UTGST</GSTRATEDUTYHEAD>\n        <GSTRATEVALUATIONTYPE>Based on Value</GSTRATEVALUATIONTYPE>\n        <GSTRATE> 2.50</GSTRATE>\n       </RATEDETAILS.LIST>\n       <RATEDETAILS.LIST>\n        <GSTRATEDUTYHEAD>IGST</GSTRATEDUTYHEAD>\n        <GSTRATEVALUATIONTYPE>Based on Value</GSTRATEVALUATIONTYPE>\n        <GSTRATE> 5</GSTRATE>\n       </RATEDETAILS.LIST>\n       <RATEDETAILS.LIST>\n        <GSTRATEDUTYHEAD>Cess</GSTRATEDUTYHEAD>\n        <GSTRATEVALUATIONTYPE>&#4; Not Applicable</GSTRATEVALUATIONTYPE>\n       </RATEDETAILS.LIST>\n       <RATEDETAILS.LIST>\n        <GSTRATEDUTYHEAD>State Cess</GSTRATEDUTYHEAD>\n        <GSTRATEVALUATIONTYPE>Based on Value</GSTRATEVALUATIONTYPE>\n       </RATEDETAILS.LIST>\n      </ALLINVENTORYENTRIES.LIST>\n      <LEDGERENTRIES.LIST>\n       <LEDGERNAME>Chanda Enterprises</LEDGERNAME>\n       <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>\n       <ISPARTYLEDGER>Yes</ISPARTYLEDGER>\n       <AMOUNT>-1575.00</AMOUNT>\n       <BILLALLOCATIONS.LIST>\n        <NAME>22</NAME>\n        <BILLTYPE>New Ref</BILLTYPE>\n        <TDSDEDUCTEEISSPECIALRATE>No</TDSDEDUCTEEISSPECIALRATE>\n        <AMOUNT>-1575.00</AMOUNT>\n       </BILLALLOCATIONS.LIST>\n      </LEDGERENTRIES.LIST>\n      <LEDGERENTRIES.LIST>\n       <LEDGERNAME>CGST</LEDGERNAME>\n       <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>\n       <ISPARTYLEDGER>No</ISPARTYLEDGER>\n       <AMOUNT>37.50</AMOUNT>\n      </LEDGERENTRIES.LIST>\n      <LEDGERENTRIES.LIST>\n       <LEDGERNAME>SGST</LEDGERNAME>\n       <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>\n       <ISPARTYLEDGER>No</ISPARTYLEDGER>\n       <AMOUNT>37.50</AMOUNT>\n      </LEDGERENTRIES.LIST>\n     </VOUCHER>\n</TALLYMESSAGE>\n</DESC>\n</BODY>\n</ENVELOPE>',
    },
    "sales-alter": {
      JSON: '{\n  "static_variables": [\n    {\n      "name": "svVchImportFormat",\n      "value": "jsonex"\n    },\n    {\n      "name": "svCurrentCompany",\n      "value": "Bhrama Enterprises"\n    }\n  ],\n  "tallymessage": [\n    {\n      "metadata": {\n        "type": "Voucher",\n        "vchtype": "Sales",\n        "remoteid": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000055",\n        "vchkey": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b34b:00000088",\n        "action": "Alter",\n        "objview": "Invoice Voucher View"\n      },\n      "date": "20250801",\n      "guid": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000055",\n      "vouchertypename": "Sales"\n    }\n  ]\n}',

      XML: '<ENVELOPE>\n    <HEADER>\n        <VERSION>1</VERSION>\n        <TALLYREQUEST>Import</TALLYREQUEST>\n        <TYPE>Data</TYPE>\n        <ID>Vouchers</ID>\n    </HEADER>\n    <BODY>\n        <DESC>\n            <STATICVARIABLES>\n                <SVVCHIMPORTFORMAT>XML</SVVCHIMPORTFORMAT>\n                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>\n            </STATICVARIABLES>\n<TALLYMESSAGE xmlns:UDF="TallyUDF">\n <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000059" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b34b:00000090" VCHTYPE="Sales" ACTION="Alter" OBJVIEW="Accounting Voucher View">\n  <DATE>20250801</DATE>\n  <GUID>f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000059</GUID>\n </VOUCHER>\n</TALLYMESSAGE>\n</DESC>\n</BODY>\n</ENVELOPE>',
    },
    "sales-delete": {
      JSON: '{\n  "static_variables": [\n    {\n      "name": "svVchImportFormat",\n      "value": "jsonex"\n    },\n    {\n      "name": "svCurrentCompany",\n      "value": "Bhrama Enterprises"\n    }\n  ],\n  "tallymessage": [\n    {\n      "metadata": {\n        "type": "Voucher",\n        "vchtype": "Sales",\n        "remoteid": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000055",\n        "vchkey": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b34b:00000088",\n        "action": "Delete",\n        "objview": "Invoice Voucher View"\n      },\n      "guid": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000055"\n    }\n  ]\n}',

      XML: '<ENVELOPE>\n    <HEADER>\n        <VERSION>1</VERSION>\n        <TALLYREQUEST>Import</TALLYREQUEST>\n        <TYPE>Data</TYPE>\n        <ID>Vouchers</ID>\n    </HEADER>\n    <BODY>\n        <DESC>\n            <STATICVARIABLES>\n                <SVVCHIMPORTFORMAT>XML</SVVCHIMPORTFORMAT>\n                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>\n            </STATICVARIABLES>\n<TALLYMESSAGE xmlns:UDF="TallyUDF">\n <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000059" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b34b:00000090" VCHTYPE="Sales" ACTION="Delete" OBJVIEW="Accounting Voucher View">\n  <GUID>f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000059</GUID>\n </VOUCHER>\n</TALLYMESSAGE>\n</DESC>\n</BODY>\n</ENVELOPE>',
    },
    "sales-pull-all": {
      JSON: '{\n  "static_variables": [\n    {\n      "name": "svExportFormat",\n      "value": "jsonex"\n    },\n    {\n      "name": "svCurrentCompany",\n      "value": "Bhrama Enterprises"\n    }\n  ],\n  "tdlmessage": [\n    {\n      "definitions": [\n        {\n          "metadata": {\n            "name": "TSPL All Sales Vouchers",\n            "type": "Collection"\n          },\n          "attributes": [\n            {\n              "Type": "Vouchers:VoucherType"\n            },\n            {\n              "Child Of": "$$VchTypeSales"\n            },\n            {\n              "Native Method": "Date, VoucherTypeName, VoucherNumber, Partyledgername"\n            }\n          ]\n        }\n      ]\n    }\n  ]\n}',

      XML: '<ENVELOPE>\n    <HEADER>\n        <VERSION>1</VERSION>\n        <TALLYREQUEST>Export</TALLYREQUEST>\n        <TYPE>Collection</TYPE>\n        <ID>TSPL ALL Sales Vouchers</ID>\n    </HEADER>\n    <BODY>\n        <DESC>\n            <STATICVARIABLES>\n                <SVEXPORTFORMAT>XML</SVEXPORTFORMAT>\n                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>\n            </STATICVARIABLES>\n<TDL>\n<TDLMESSAGE>\n  <COLLECTION NAME="TSPL ALL Sales Vouchers" ISMODIFY="No" ISFIXED="No" ISINITIALIZE="No" ISOPTION="No" ISINTERNAL="No">\n   <TYPE>Vouchers:VoucherType</TYPE>\n   <CHILDOF>$$VchTypeSales</CHILDOF>\n   <NATIVEMETHOD>Date, VoucherTypeName, VoucherNumber, Partyledgername</NATIVEMETHOD>\n  </COLLECTION>\n</TDLMESSAGE>\n</TDL>\n        </DESC>\n    </BODY>\n</ENVELOPE>',
    },
    "sales-pull-period": {
      JSON: '{\n  "static_variables": [\n    {\n      "name": "svExportFormat",\n      "value": "jsonex"\n    },\n    {\n      "name": "svCurrentCompany",\n      "value": "Bhrama Enterprises"\n    }\n  ],\n  "tdlmessage": [\n    {\n      "definitions": [\n        {\n          "metadata": {\n            "name": "TSPL Sales Vouchers",\n            "type": "Collection"\n          },\n          "attributes": [\n            {\n              "Type": "Vouchers:VoucherType"\n            },\n            {\n              "Child Of": "$$VchTypeSales"\n            },\n            {\n              "Native Method": "Date, VoucherTypeName, VoucherNumber, Partyledgername"\n            },\n            {\n              "Filters": "Period Filter"\n            }\n          ]\n        },\n        {\n          "metadata": {\n            "name": "PeriodFilter",\n            "type": "System",\n            "sys_type": "Formulae",\n            "ismodify": true\n          },\n          "value": "$Date >= ($$Date:\\"01-05-2025\\") AND $Date <= ($$Date:\\"10-05-2025\\")"\n        }\n      ]\n    }\n  ]\n}',

      XML: '<ENVELOPE>\n    <HEADER>\n        <VERSION>1</VERSION>\n        <TALLYREQUEST>Export</TALLYREQUEST>\n        <TYPE>Collection</TYPE>\n        <ID>TSPL Sales Vouchers</ID>\n    </HEADER>\n    <BODY>\n        <DESC>\n            <STATICVARIABLES>\n                <SVEXPORTFORMAT>XML</SVEXPORTFORMAT>\n                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>\n            </STATICVARIABLES>\n<TDL>\n<TDLMESSAGE>\n  <COLLECTION NAME="TSPL Sales Vouchers" ISMODIFY="No" ISFIXED="No" ISINITIALIZE="No" ISOPTION="No" ISINTERNAL="No">\n   <TYPE>Vouchers:VoucherType</TYPE>\n   <CHILDOF>$$VchTypeSales</CHILDOF>\n   <NATIVEMETHOD>Date, VoucherTypeName, VoucherNumber, Partyledgername</NATIVEMETHOD>\n   <FILTERS>Period Filter</FILTERS>\n  </COLLECTION>\n  <SYSTEM TYPE="Formulae" NAME="PeriodFilter" ISMODIFY="Yes" ISFIXED="No" ISINTERNAL="No">$Date &gt;= ($$Date:"01-05-2025") AND $Date &lt;= ($$Date:"10-05-2025")  </SYSTEM>\n</TDLMESSAGE>\n</TDL>\n        </DESC>\n    </BODY>\n</ENVELOPE>',
    },
    /* Purchase */
    "purchase-create-item": {
      JSON: '{\n  "tallymessage": [\n    {\n      "metadata": {\n        "type": "Voucher",\n        "vchtype": "Purchase",\n        "action": "Create",\n        "objview": "Invoice Voucher View"\n      },\n      "date": "20260301",\n      "vchstatusdate": "20260301",\n      "gstregistrationtype": "\\u0004 Unknown",\n      "statename": "Alabama",\n      "countryofresidence": "United States of America",\n      "vouchertypename": "Purchase",\n      "partyname": "International Party",\n      "partyledgername": "International Party",\n      "basicbuyername": "Bhrama Enterprises",\n      "cmpgstregistrationtype": "Regular",\n      "partymailingname": "International Party",\n      "consigneegstin": "29AAECP4424C1ZN",\n      "consigneemailingname": "Bhrama Enterprises",\n      "consigneestatename": "Karnataka",\n      "cmpgststate": "Karnataka",\n      "consigneecountryname": "India",\n      "basicbasepartyname": "International Party",\n      "effectivedate": "20260301",\n      "isinvoice": true,\n      "allinventoryentries": [\n        {\n          "stockitemname": "Computer US",\n          "isdeemedpositive": true,\n          "rate": "10000.00/nos",\n          "amount": "-200000.00",\n          "actualqty": " 20 nos",\n          "billedqty": " 20 nos",\n          "batchallocations": [\n            {\n              "godownname": "Main Location",\n              "batchname": "Primary Batch",\n              "amount": "-200000.00",\n              "actualqty": " 20 nos",\n              "billedqty": " 20 nos"\n            }\n          ],\n          "accountingallocations": [\n            {\n              "ledgername": "Purchase",\n              "isdeemedpositive": true,\n              "ispartyledger": false,\n              "amount": "-200000.00"\n            }\n          ]\n        }\n      ],\n      "ledgerentries": [\n        {\n          "ledgername": "International Party",\n          "isdeemedpositive": false,\n          "ispartyledger": true,\n          "amount": "200000.00",\n          "billallocations": [\n            {\n              "name": "12",\n              "billtype": "New Ref",\n              "amount": "200000.00"\n            }\n          ]\n        }\n      ]\n    }\n  ]\n}',

      XML: '<ENVELOPE>\n    <HEADER>\n        <VERSION>1</VERSION>\n        <TALLYREQUEST>Import</TALLYREQUEST>\n        <TYPE>Data</TYPE>\n        <ID>Vouchers</ID>\n    </HEADER>\n    <BODY>\n        <DESC>\n            <STATICVARIABLES>\n                <SVVCHIMPORTFORMAT>XML</SVVCHIMPORTFORMAT>\n                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>\n            </STATICVARIABLES>\n<TALLYMESSAGE xmlns:UDF="TallyUDF">\n  <VOUCHER VCHTYPE="Purchase" ACTION="Create" OBJVIEW="Invoice Voucher View">\n      <DATE>20260301</DATE>\n      <VCHSTATUSDATE>20260301</VCHSTATUSDATE>\n      <GSTREGISTRATIONTYPE>&#4; Unknown</GSTREGISTRATIONTYPE>\n      <STATENAME>Alabama</STATENAME>\n      <COUNTRYOFRESIDENCE>United States of America</COUNTRYOFRESIDENCE>\n      <VOUCHERTYPENAME>Purchase</VOUCHERTYPENAME>\n      <PARTYNAME>International Party</PARTYNAME>\n      <PARTYLEDGERNAME>International Party</PARTYLEDGERNAME>\n      <BASICBUYERNAME>Bhrama Enterprises</BASICBUYERNAME>\n      <CMPGSTREGISTRATIONTYPE>Regular</CMPGSTREGISTRATIONTYPE>\n      <PARTYMAILINGNAME>International Party</PARTYMAILINGNAME>\n      <CONSIGNEEGSTIN>29AAECP4424C1ZN</CONSIGNEEGSTIN>\n      <CONSIGNEEMAILINGNAME>Bhrama Enterprises</CONSIGNEEMAILINGNAME>\n      <CONSIGNEESTATENAME>Karnataka</CONSIGNEESTATENAME>\n      <CMPGSTSTATE>Karnataka</CMPGSTSTATE>\n      <CONSIGNEECOUNTRYNAME>India</CONSIGNEECOUNTRYNAME>\n      <BASICBASEPARTYNAME>International Party</BASICBASEPARTYNAME>\n      <PERSISTEDVIEW>Invoice Voucher View</PERSISTEDVIEW>\n      <EFFECTIVEDATE>20260301</EFFECTIVEDATE>\n      <ISINVOICE>Yes</ISINVOICE>\n      <ALLINVENTORYENTRIES.LIST>\n       <STOCKITEMNAME>Computer US</STOCKITEMNAME>\n       <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>\n       <RATE>10000.00/nos</RATE>\n       <AMOUNT>-200000.00</AMOUNT>\n       <ACTUALQTY> 20 nos</ACTUALQTY>\n       <BILLEDQTY> 20 nos</BILLEDQTY>\n       <BATCHALLOCATIONS.LIST>\n        <GODOWNNAME>Main Location</GODOWNNAME>\n        <BATCHNAME>Primary Batch</BATCHNAME>\n        <AMOUNT>-200000.00</AMOUNT>\n        <ACTUALQTY> 20 nos</ACTUALQTY>\n        <BILLEDQTY> 20 nos</BILLEDQTY>\n       </BATCHALLOCATIONS.LIST>\n       <ACCOUNTINGALLOCATIONS.LIST>\n        <LEDGERNAME>Purchase</LEDGERNAME>\n        <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>\n        <ISPARTYLEDGER>No</ISPARTYLEDGER>\n        <AMOUNT>-200000.00</AMOUNT>\n       </ACCOUNTINGALLOCATIONS.LIST>\n      </ALLINVENTORYENTRIES.LIST>\n      <LEDGERENTRIES.LIST>\n       <LEDGERNAME>International Party</LEDGERNAME>\n       <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>\n       <ISPARTYLEDGER>Yes</ISPARTYLEDGER>\n       <AMOUNT>200000.00</AMOUNT>\n       <BILLALLOCATIONS.LIST>\n        <NAME>12</NAME>\n        <BILLTYPE>New Ref</BILLTYPE>\n        <AMOUNT>200000.00</AMOUNT>\n       </BILLALLOCATIONS.LIST>\n      </LEDGERENTRIES.LIST>\n     </VOUCHER>\n</TALLYMESSAGE>\n</DESC>\n</BODY>\n</ENVELOPE>',
    },
    "purchase-create-gst": {
      JSON: '{\n  "static_variables": [\n    {\n      "name": "svVchImportFormat",\n      "value": "jsonex"\n    },\n    {\n      "name": "svCurrentCompany",\n      "value": "Bhrama Enterprises"\n    }\n  ],\n  "tallymessage": [\n    {\n      "metadata": {\n        "type": "Voucher",\n        "vchtype": "Purchase",\n        "action": "Create",\n        "objview": "Invoice Voucher View"\n      },\n      "date": "20250901",\n      "vchstatusdate": "20250901",\n      "gstregistrationtype": "Regular",\n      "vatdealertype": "Regular",\n      "statename": "Karnataka",\n      "countryofresidence": "India",\n      "partygstin": "29AAACH1004N1ZQ",\n      "placeofsupply": "Karnataka",\n      "vouchertypename": "Purchase",\n      "partyname": "Mondal Enterprises",\n      "gstregistration": {\n        "value": "Karnataka Registration",\n        "taxtype": "GST",\n        "taxregistration": "29AAECP4424C1ZN"\n      },\n      "cmpgstin": "29AAECP4424C1ZN",\n      "partyledgername": "Mondal Enterprises",\n      "basicbuyername": "Bhrama Enterprises",\n      "cmpgstregistrationtype": "Regular",\n      "partymailingname": "Mondal Enterprises",\n      "consigneegstin": "29AAECP4424C1ZN",\n      "consigneemailingname": "Bhrama Enterprises",\n      "consigneestatename": "Karnataka",\n      "cmpgststate": "Karnataka",\n      "consigneecountryname": "India",\n      "basicbasepartyname": "Mondal Enterprises",\n      "effectivedate": "20250901",\n      "isinvoice": true,\n      "allinventoryentries": [\n        {\n          "stockitemname": "Decaf Coffee",\n          "gstovrdnineligibleitc": "\\u0004 Not Applicable",\n          "gstovrdnisrevchargeappl": "\\u0004 Not Applicable",\n          "gstovrdntaxability": "Taxable",\n          "gstsourcetype": "Stock Item",\n          "gstitemsource": "Decaf Coffee",\n          "hsnsourcetype": "Stock Item",\n          "hsnitemsource": "Decaf Coffee",\n          "gstovrdntypeofsupply": "Goods",\n          "gstrateinferapplicability": "As per Masters/Company",\n          "gsthsninferapplicability": "As per Masters/Company",\n          "isdeemedpositive": true,\n          "rate": "15.00/nos",\n          "amount": "-1500.00",\n          "actualqty": " 100 nos",\n          "billedqty": " 100 nos",\n          "batchallocations": [\n            {\n              "godownname": "Main Location",\n              "batchname": "Primary Batch",\n              "amount": "-1500.00",\n              "actualqty": " 100 nos",\n              "billedqty": " 100 nos"\n            }\n          ],\n          "accountingallocations": [\n            {\n              "ledgername": "GST Purchase",\n              "isdeemedpositive": true,\n              "ispartyledger": false,\n              "amount": "-1500.00"\n            }\n          ],\n          "ratedetails": [\n            {\n              "gstratedutyhead": "CGST",\n              "gstratevaluationtype": "Based on Value",\n              "gstrate": " 2"\n            },\n            {\n              "gstratedutyhead": "SGST/UTGST",\n              "gstratevaluationtype": "Based on Value",\n              "gstrate": " 2"\n            },\n            {\n              "gstratedutyhead": "IGST",\n              "gstratevaluationtype": "Based on Value",\n              "gstrate": " 4"\n            },\n            {\n              "gstratedutyhead": "Cess",\n              "gstratevaluationtype": "\\u0004 Not Applicable"\n            },\n            {\n              "gstratedutyhead": "State Cess",\n              "gstratevaluationtype": "Based on Value"\n            }\n          ]\n        }\n      ],\n      "ledgerentries": [\n        {\n          "ledgername": "Mondal Enterprises",\n          "isdeemedpositive": false,\n          "ispartyledger": true,\n          "amount": "1560.00",\n          "billallocations": [\n            {\n              "name": "46",\n              "billtype": "New Ref",\n              "amount": "1560.00"\n            }\n          ]\n        },\n        {\n          "ledgername": "CGST",\n          "isdeemedpositive": true,\n          "ispartyledger": false,\n          "amount": "-30.00"\n        },\n        {\n          "ledgername": "SGST",\n          "isdeemedpositive": true,\n          "ispartyledger": false,\n          "amount": "-30.00"\n        }\n      ]\n    }\n  ]\n}',

      XML: '<ENVELOPE>\n    <HEADER>\n        <VERSION>1</VERSION>\n        <TALLYREQUEST>Import</TALLYREQUEST>\n        <TYPE>Data</TYPE>\n        <ID>Vouchers</ID>\n    </HEADER>\n    <BODY>\n        <DESC>\n            <STATICVARIABLES>\n                <SVVCHIMPORTFORMAT>XML</SVVCHIMPORTFORMAT>\n                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>\n            </STATICVARIABLES>\n<TALLYMESSAGE xmlns:UDF="TallyUDF">\n  <VOUCHER VCHTYPE="Purchase" ACTION="Create" OBJVIEW="Invoice Voucher View">\n      <DATE>20250901</DATE>\n      <GSTREGISTRATIONTYPE>Regular</GSTREGISTRATIONTYPE>\n      <VATDEALERTYPE>Regular</VATDEALERTYPE>\n      <STATENAME>Karnataka</STATENAME>\n      <COUNTRYOFRESIDENCE>India</COUNTRYOFRESIDENCE>\n      <PARTYGSTIN>29AAACH1004N1ZQ</PARTYGSTIN>\n      <PLACEOFSUPPLY>Karnataka</PLACEOFSUPPLY>\n      <VOUCHERTYPENAME>Purchase</VOUCHERTYPENAME>\n      <PARTYNAME>Mondal Enterprises</PARTYNAME>\n      <GSTREGISTRATION TAXTYPE="GST" TAXREGISTRATION="29AAECP4424C1ZN">Karnataka Registration</GSTREGISTRATION>\n      <CMPGSTIN>29AAECP4424C1ZN</CMPGSTIN>\n      <PARTYLEDGERNAME>Mondal Enterprises</PARTYLEDGERNAME>\n      <BASICBUYERNAME>Bhrama Enterprises</BASICBUYERNAME>\n      <CMPGSTREGISTRATIONTYPE>Regular</CMPGSTREGISTRATIONTYPE>\n      <PARTYMAILINGNAME>Mondal Enterprises</PARTYMAILINGNAME>\n      <CONSIGNEEGSTIN>29AAECP4424C1ZN</CONSIGNEEGSTIN>\n      <CONSIGNEEMAILINGNAME>Bhrama Enterprises</CONSIGNEEMAILINGNAME>\n      <CONSIGNEESTATENAME>Karnataka</CONSIGNEESTATENAME>\n      <CMPGSTSTATE>Karnataka</CMPGSTSTATE>\n      <CONSIGNEECOUNTRYNAME>India</CONSIGNEECOUNTRYNAME>\n      <BASICBASEPARTYNAME>Mondal Enterprises</BASICBASEPARTYNAME>\n      <PERSISTEDVIEW>Invoice Voucher View</PERSISTEDVIEW>\n      <VCHENTRYMODE>Item Invoice</VCHENTRYMODE>\n      <EFFECTIVEDATE>20250901</EFFECTIVEDATE>\n      <ISINVOICE>Yes</ISINVOICE>\n      <ALLINVENTORYENTRIES.LIST>\n       <STOCKITEMNAME>Decaf Coffee</STOCKITEMNAME>\n       <GSTOVRDNINELIGIBLEITC>&#4; Not Applicable</GSTOVRDNINELIGIBLEITC>\n       <GSTOVRDNISREVCHARGEAPPL>&#4; Not Applicable</GSTOVRDNISREVCHARGEAPPL>\n       <GSTOVRDNTAXABILITY>Taxable</GSTOVRDNTAXABILITY>\n       <GSTSOURCETYPE>Stock Item</GSTSOURCETYPE>\n       <GSTITEMSOURCE>Decaf Coffee</GSTITEMSOURCE>\n       <HSNSOURCETYPE>Stock Item</HSNSOURCETYPE>\n       <HSNITEMSOURCE>Decaf Coffee</HSNITEMSOURCE>\n       <GSTOVRDNTYPEOFSUPPLY>Goods</GSTOVRDNTYPEOFSUPPLY>\n       <GSTRATEINFERAPPLICABILITY>As per Masters/Company</GSTRATEINFERAPPLICABILITY>\n       <GSTHSNINFERAPPLICABILITY>As per Masters/Company</GSTHSNINFERAPPLICABILITY>\n       <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>\n       <RATE>15.00/nos</RATE>\n       <AMOUNT>-1500.00</AMOUNT>\n       <ACTUALQTY> 100 nos</ACTUALQTY>\n       <BILLEDQTY> 100 nos</BILLEDQTY>\n       <BATCHALLOCATIONS.LIST>\n        <GODOWNNAME>Main Location</GODOWNNAME>\n        <BATCHNAME>Primary Batch</BATCHNAME>\n        <DESTINATIONGODOWNNAME>Main Location</DESTINATIONGODOWNNAME>\n        <AMOUNT>-1500.00</AMOUNT>\n        <ACTUALQTY> 100 nos</ACTUALQTY>\n        <BILLEDQTY> 100 nos</BILLEDQTY>\n       </BATCHALLOCATIONS.LIST>\n       <ACCOUNTINGALLOCATIONS.LIST>\n        <LEDGERNAME>GST Purchase</LEDGERNAME>\n        <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>\n        <ISPARTYLEDGER>No</ISPARTYLEDGER>\n        <AMOUNT>-1500.00</AMOUNT>\n       </ACCOUNTINGALLOCATIONS.LIST>\n       <RATEDETAILS.LIST>\n        <GSTRATEDUTYHEAD>CGST</GSTRATEDUTYHEAD>\n        <GSTRATEVALUATIONTYPE>Based on Value</GSTRATEVALUATIONTYPE>\n        <GSTRATE> 2</GSTRATE>\n       </RATEDETAILS.LIST>\n       <RATEDETAILS.LIST>\n        <GSTRATEDUTYHEAD>SGST/UTGST</GSTRATEDUTYHEAD>\n        <GSTRATEVALUATIONTYPE>Based on Value</GSTRATEVALUATIONTYPE>\n        <GSTRATE> 2</GSTRATE>\n       </RATEDETAILS.LIST>\n       <RATEDETAILS.LIST>\n        <GSTRATEDUTYHEAD>IGST</GSTRATEDUTYHEAD>\n        <GSTRATEVALUATIONTYPE>Based on Value</GSTRATEVALUATIONTYPE>\n        <GSTRATE> 4</GSTRATE>\n       </RATEDETAILS.LIST>\n       <RATEDETAILS.LIST>\n        <GSTRATEDUTYHEAD>Cess</GSTRATEDUTYHEAD>\n        <GSTRATEVALUATIONTYPE>&#4; Not Applicable</GSTRATEVALUATIONTYPE>\n       </RATEDETAILS.LIST>\n       <RATEDETAILS.LIST>\n        <GSTRATEDUTYHEAD>State Cess</GSTRATEDUTYHEAD>\n        <GSTRATEVALUATIONTYPE>Based on Value</GSTRATEVALUATIONTYPE>\n       </RATEDETAILS.LIST>\n      </ALLINVENTORYENTRIES.LIST>\n      <LEDGERENTRIES.LIST>\n       <LEDGERNAME>Mondal Enterprises</LEDGERNAME>\n       <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>\n       <ISPARTYLEDGER>Yes</ISPARTYLEDGER>\n       <AMOUNT>1560.00</AMOUNT>\n       <BILLALLOCATIONS.LIST>\n        <NAME>23</NAME>\n        <BILLTYPE>New Ref</BILLTYPE>\n        <AMOUNT>1560.00</AMOUNT>\n       </BILLALLOCATIONS.LIST>\n      </LEDGERENTRIES.LIST>\n      <LEDGERENTRIES.LIST>\n       <LEDGERNAME>CGST</LEDGERNAME>\n       <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>\n       <ISPARTYLEDGER>No</ISPARTYLEDGER>\n       <AMOUNT>-30.00</AMOUNT>\n      </LEDGERENTRIES.LIST>\n      <LEDGERENTRIES.LIST>\n       <LEDGERNAME>SGST</LEDGERNAME>\n       <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>\n       <ISPARTYLEDGER>No</ISPARTYLEDGER>\n       <AMOUNT>-30.00</AMOUNT>\n      </LEDGERENTRIES.LIST>\n     </VOUCHER>\n</TALLYMESSAGE>\n</DESC>\n</BODY>\n</ENVELOPE>',
    },
    "purchase-alter": {
      JSON: '{\n  "static_variables": [\n    {\n      "name": "svVchImportFormat",\n      "value": "jsonex"\n    },\n    {\n      "name": "svCurrentCompany",\n      "value": "Bhrama Enterprises"\n    }\n  ],\n  "tallymessage": [\n    {\n      "metadata": {\n        "type": "Voucher",\n        "vchtype": "Purchase",\n        "remoteid": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000075",\n        "vchkey": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b34b:000000f8",\n        "action": "Alter",\n        "objview": "Invoice Voucher View"\n      },\n      "date": "20250802",\n      "effectivedate": "20250802",\n      "guid": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000075"\n    }\n  ]\n}',

      XML: '<ENVELOPE>\n    <HEADER>\n        <VERSION>1</VERSION>\n        <TALLYREQUEST>Import</TALLYREQUEST>\n        <TYPE>Data</TYPE>\n        <ID>Vouchers</ID>\n    </HEADER>\n    <BODY>\n        <DESC>\n            <STATICVARIABLES>\n                <SVVCHIMPORTFORMAT>XML</SVVCHIMPORTFORMAT>\n                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>\n            </STATICVARIABLES>\n<TALLYMESSAGE xmlns:UDF="TallyUDF">\n<VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000079" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b34b:000000f8" VCHTYPE="Purchase" ACTION="Alter" OBJVIEW="Invoice Voucher View">\n  <DATE>20250802</DATE>\n  <EFFECTIVEDATE>20250802</EFFECTIVEDATE>\n  <GUID>f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000079</GUID>\n </VOUCHER>\n</TALLYMESSAGE>\n</DESC>\n</BODY>\n</ENVELOPE>',
    },
    "purchase-delete": {
      JSON: '{\n  "static_variables": [\n    {\n      "name": "svVchImportFormat",\n      "value": "jsonex"\n    },\n    {\n      "name": "svCurrentCompany",\n      "value": "Bhrama Enterprises"\n    }\n  ],\n  "tallymessage": [\n    {\n      "metadata": {\n        "type": "Voucher",\n        "vchtype": "Purchase",\n        "remoteid": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000083",\n        "vchkey": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b400:00000010",\n        "action": "Delete",\n        "objview": "Invoice Voucher View"\n      },\n      "guid": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000083"\n    }\n  ]\n}',

      XML: '<ENVELOPE>\n    <HEADER>\n        <VERSION>1</VERSION>\n        <TALLYREQUEST>Import</TALLYREQUEST>\n        <TYPE>Data</TYPE>\n        <ID>Vouchers</ID>\n    </HEADER>\n    <BODY>\n        <DESC>\n            <STATICVARIABLES>\n                <SVVCHIMPORTFORMAT>XML</SVVCHIMPORTFORMAT>\n                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>\n            </STATICVARIABLES>\n<TALLYMESSAGE xmlns:UDF="TallyUDF">\n <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000083" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b400:00000010" VCHTYPE="Purchase" ACTION="Delete" OBJVIEW="Invoice Voucher View">\n<GUID>f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000083</GUID>\n </VOUCHER>\n</TALLYMESSAGE>\n</DESC>\n</BODY>\n</ENVELOPE>',
    },
    "purchase-pull-all": {
      JSON: '{\n  "static_variables": [\n    {\n      "name": "svExportFormat",\n      "value": "jsonex"\n    },\n    {\n      "name": "svCurrentCompany",\n      "value": "Bhrama Enterprises"\n    }\n  ],\n  "tdlmessage": [\n    {\n      "definitions": [\n        {\n          "metadata": {\n            "name": "TSPL All Purchase Vouchers",\n            "type": "Collection"\n          },\n          "attributes": [\n            {\n              "Type": "Vouchers:VoucherType"\n            },\n            {\n              "Child Of": "$$VchTypePurchase"\n            },\n            {\n              "Native Method": "Date, VoucherTypeName, VoucherNumber, Partyledgername"\n            }\n          ]\n        }\n      ]\n    }\n  ]\n}',

      XML: '<ENVELOPE>\n    <HEADER>\n        <VERSION>1</VERSION>\n        <TALLYREQUEST>Export</TALLYREQUEST>\n        <TYPE>Collection</TYPE>\n        <ID>TSPL All Purchase Vouchers</ID>\n    </HEADER>\n    <BODY>\n        <DESC>\n            <STATICVARIABLES>\n                <SVEXPORTFORMAT>XML</SVEXPORTFORMAT>\n                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>\n            </STATICVARIABLES>\n<TDL>\n<TDLMESSAGE>\n  <COLLECTION NAME="TSPL All Purchase Vouchers" ISMODIFY="No" ISFIXED="No" ISINITIALIZE="No" ISOPTION="No" ISINTERNAL="No">\n   <TYPE>Vouchers:VoucherType</TYPE>\n   <CHILDOF>$$VchTypePurchase</CHILDOF>\n   <NATIVEMETHOD>Date, VoucherTypeName, VoucherNumber, Partyledgername</NATIVEMETHOD>\n  </COLLECTION>\n</TDLMESSAGE>\n</TDL>\n        </DESC>\n    </BODY>\n</ENVELOPE>',
    },
    "purchase-pull-period": {
      JSON: '{\n  "static_variables": [\n    {\n      "name": "svExportFormat",\n      "value": "jsonex"\n    },\n    {\n      "name": "svCurrentCompany",\n      "value": "Bhrama Enterprises"\n    }\n  ],\n  "tdlmessage": [\n    {\n      "definitions": [\n        {\n          "metadata": {\n            "name": "TSPL Purchase Vouchers",\n            "type": "Collection"\n          },\n          "attributes": [\n            {\n              "Type": "Vouchers:VoucherType"\n            },\n            {\n              "Child Of": "$$VchTypePurchase"\n            },\n            {\n              "Native Method": "Date, VoucherTypeName, VoucherNumber, Partyledgername"\n            },\n            {\n              "Filters": "Period Filter"\n            }\n          ]\n        },\n        {\n          "metadata": {\n            "name": "PeriodFilter",\n            "type": "System",\n            "sys_type": "Formulae",\n            "ismodify": true\n          },\n          "value": "$Date >= ($$Date:\\"01-07-2025\\") AND $Date <= ($$Date:\\"10-07-2025\\")"\n        }\n      ]\n    }\n  ]\n}',

      XML: '<ENVELOPE>\n    <HEADER>\n        <VERSION>1</VERSION>\n        <TALLYREQUEST>Export</TALLYREQUEST>\n        <TYPE>Collection</TYPE>\n        <ID>TSPL Purchase Vouchers</ID>\n    </HEADER>\n    <BODY>\n        <DESC>\n            <STATICVARIABLES>\n                <SVEXPORTFORMAT>XML</SVEXPORTFORMAT>\n                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>\n            </STATICVARIABLES>\n<TDL>\n<TDLMESSAGE>\n  <COLLECTION NAME="TSPL Purchase Vouchers" ISMODIFY="No" ISFIXED="No" ISINITIALIZE="No" ISOPTION="No" ISINTERNAL="No">\n   <TYPE>Vouchers:VoucherType</TYPE>\n   <CHILDOF>$$VchTypePurchase</CHILDOF>\n   <NATIVEMETHOD>Date, VoucherTypeName, VoucherNumber, Partyledgername</NATIVEMETHOD>\n   <FILTERS>Period Filter</FILTERS>\n  </COLLECTION>\n  <SYSTEM TYPE="Formulae" NAME="PeriodFilter" ISMODIFY="Yes" ISFIXED="No" ISINTERNAL="No">$Date &gt;= ($$Date:"01-07-2025") AND $Date &lt;= ($$Date:"10-07-2025")  </SYSTEM>\n</TDLMESSAGE>\n</TDL>\n        </DESC>\n    </BODY>\n</ENVELOPE>',
    },
    /* Reports — Trial Balance */
    "pull-trial-balance-period": {
      JSON: '{\n  "static_variables": [\n    {\n      "name": "svExportFormat",\n      "value": "jsonex"\n    },\n    {\n      "name": "svCurrentCompany",\n      "value": "Bhrama Enterprises"\n    },\n    {\n      "name": "svFromDate",\n      "value": "20250401"\n    },\n    {\n      "name": "svToDate",\n      "value": "20250430"\n    }\n  ]\n}',
      XML: '<ENVELOPE>\n  <HEADER>\n    <VERSION>1</VERSION>\n    <TALLYREQUEST>Export</TALLYREQUEST>\n    <TYPE>Data</TYPE>\n    <ID>Trial Balance</ID>\n  </HEADER>\n  <BODY>\n    <DESC>\n      <STATICVARIABLES>\n        <SVEXPORTFORMAT>XML</SVEXPORTFORMAT>\n        <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>\n        <SVFROMDATE>20250401</SVFROMDATE>\n        <SVTODATE>20250430</SVTODATE>\n      </STATICVARIABLES>\n    </DESC>\n  </BODY>\n</ENVELOPE>',
    },
    "pull-trial-balance-detailed": {
      JSON: '{\n  "static_variables": [\n    {\n      "name": "svExportFormat",\n      "value": "jsonex"\n    },\n    {\n      "name": "svCurrentCompany",\n      "value": "Bhrama Enterprises"\n    },\n    {\n      "name": "svFromDate",\n      "value": "20250401"\n    },\n    {\n      "name": "svToDate",\n      "value": "20250430"\n    },\n    {\n      "name": "ExplodeFlag",\n      "value": "Yes"\n    },\n    {\n      "name": "ExplodeAllLevels",\n      "value": "Yes"\n    }\n  ]\n}',
      XML: '<ENVELOPE>\n  <HEADER>\n    <VERSION>1</VERSION>\n    <TALLYREQUEST>Export</TALLYREQUEST>\n    <TYPE>Data</TYPE>\n    <ID>Trial Balance</ID>\n  </HEADER>\n  <BODY>\n    <DESC>\n      <STATICVARIABLES>\n        <SVEXPORTFORMAT>XML</SVEXPORTFORMAT>\n        <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>\n        <SVFROMDATE>20250401</SVFROMDATE>\n        <SVTODATE>20250430</SVTODATE>\n        <EXPLODEFLAG>Yes</EXPLODEFLAG>\n        <EXPLODEALLLEVELS>Yes</EXPLODEALLLEVELS>\n      </STATICVARIABLES>\n    </DESC>\n  </BODY>\n</ENVELOPE>',
    },
    "pull-trial-balance-plain": {
      JSON: '{\n  "static_variables": [\n    {\n      "name": "svExportFormat",\n      "value": "jsonex"\n    },\n    {\n      "name": "svCurrentCompany",\n      "value": "Bhrama Enterprises"\n    },\n    {\n      "name": "svFromDate",\n      "value": "20250401"\n    },\n    {\n      "name": "svToDate",\n      "value": "20250430"\n    }\n  ],\n  "tdlmessage": [\n    {\n      "definitions": [\n        {\n          "metadata": {\n            "name": "Trial Balance",\n            "type": "Report",\n            "ismodify": true\n          },\n          "attributes": [\n            {\n              "Plain Xml": "Yes"\n            }\n          ]\n        }\n      ]\n    }\n  ]\n}',
      XML: '<ENVELOPE>\n  <HEADER>\n    <VERSION>1</VERSION>\n    <TALLYREQUEST>Export</TALLYREQUEST>\n    <TYPE>Data</TYPE>\n    <ID>Trial Balance</ID>\n  </HEADER>\n  <BODY>\n    <DESC>\n      <STATICVARIABLES>\n        <SVEXPORTFORMAT>XML</SVEXPORTFORMAT>\n        <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>\n        <SVFROMDATE>20250401</SVFROMDATE>\n        <SVTODATE>20250430</SVTODATE>\n      </STATICVARIABLES>\n      <TDL>\n        <TDLMESSAGE>\n          <REPORT NAME="Trial Balance" ISMODIFY="Yes" ISFIXED="No" ISINITIALIZE="No" ISOPTION="No" ISINTERNAL="No">\n            <PLAINXML>Yes</PLAINXML>\n          </REPORT>\n        </TDLMESSAGE>\n      </TDL>\n    </DESC>\n  </BODY>\n</ENVELOPE>',
    },
    "pull-trial-balance-empty-fields": {
      JSON: '{\n  "static_variables": [\n    {\n      "name": "svExportFormat",\n      "value": "jsonex"\n    },\n    {\n      "name": "svCurrentCompany",\n      "value": "Bhrama Enterprises"\n    },\n    {\n      "name": "svFromDate",\n      "value": "20250401"\n    },\n    {\n      "name": "svToDate",\n      "value": "20250430"\n    }\n  ],\n  "tdlmessage": [\n    {\n      "definitions": [\n        {\n          "metadata": {\n            "name": "Trial Balance",\n            "type": "Report",\n            "ismodify": true\n          },\n          "attributes": [\n            {\n              "Export Empty Fields": "Yes"\n            }\n          ]\n        }\n      ]\n    }\n  ]\n}',
      XML: '<ENVELOPE>\n  <HEADER>\n    <VERSION>1</VERSION>\n    <TALLYREQUEST>Export</TALLYREQUEST>\n    <TYPE>Data</TYPE>\n    <ID>Trial Balance</ID>\n  </HEADER>\n  <BODY>\n    <DESC>\n      <STATICVARIABLES>\n        <SVEXPORTFORMAT>XML</SVEXPORTFORMAT>\n        <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>\n        <SVFROMDATE>20250401</SVFROMDATE>\n        <SVTODATE>20250430</SVTODATE>\n      </STATICVARIABLES>\n    </DESC>\n  </BODY>\n</ENVELOPE>',
    },
    "pull-trial-balance-ledger-wise": {
      JSON: '{\n  "static_variables": [\n    {\n      "name": "svExportFormat",\n      "value": "jsonex"\n    },\n    {\n      "name": "svCurrentCompany",\n      "value": "Bhrama Enterprises"\n    },\n    {\n      "name": "svFromDate",\n      "value": "20250401"\n    },\n    {\n      "name": "svToDate",\n      "value": "20250430"\n    },\n    {\n      "name": "IsLedgerwise",\n      "value": "Yes"\n    }\n  ]\n}',
      XML: '<ENVELOPE>\n  <HEADER>\n    <VERSION>1</VERSION>\n    <TALLYREQUEST>Export</TALLYREQUEST>\n    <TYPE>Data</TYPE>\n    <ID>Trial Balance</ID>\n  </HEADER>\n  <BODY>\n    <DESC>\n      <STATICVARIABLES>\n        <SVEXPORTFORMAT>XML</SVEXPORTFORMAT>\n        <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>\n        <SVFROMDATE>20250401</SVFROMDATE>\n        <SVTODATE>20250430</SVTODATE>\n        <ISLEDGERWISE>Yes</ISLEDGERWISE>\n      </STATICVARIABLES>\n    </DESC>\n  </BODY>\n</ENVELOPE>',
    },
    "pull-trial-balance-group": {
      JSON: '{\n  "static_variables": [\n    {\n      "name": "svExportFormat",\n      "value": "jsonex"\n    },\n    {\n      "name": "svCurrentCompany",\n      "value": "Bhrama Enterprises"\n    },\n    {\n      "name": "svFromDate",\n      "value": "20250401"\n    },\n    {\n      "name": "svToDate",\n      "value": "20250430"\n    }\n  ],\n  "tdlmessage": [\n    {\n      "definitions": [\n        {\n          "metadata": {\n            "name": "Trial Balance",\n            "type": "Report",\n            "ismodify": true\n          },\n          "attributes": [\n            {\n              "Set": "Groupname :\\"Bank Accounts\\""\n            }\n          ]\n        }\n      ]\n    }\n  ]\n}',
      XML: '<ENVELOPE>\n  <HEADER>\n    <VERSION>1</VERSION>\n    <TALLYREQUEST>Export</TALLYREQUEST>\n    <TYPE>Data</TYPE>\n    <ID>Trial Balance</ID>\n  </HEADER>\n  <BODY>\n    <DESC>\n      <STATICVARIABLES>\n        <SVEXPORTFORMAT>XML</SVEXPORTFORMAT>\n        <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>\n        <SVFROMDATE>20250401</SVFROMDATE>\n        <SVTODATE>20250430</SVTODATE>\n      </STATICVARIABLES>\n      <TDL>\n        <TDLMESSAGE>\n          <REPORT NAME="TrialBalance" ISMODIFY="Yes">\n            <ADD>SET: Groupname :"Bank Accounts"</ADD>\n          </REPORT>\n        </TDLMESSAGE>\n      </TDL>\n    </DESC>\n  </BODY>\n</ENVELOPE>',
    },
    /* Reports — Sales Register */
    "pull-sales-register-period": {
      JSON: '{\n  "static_variables": [\n    {\n      "name": "svExportFormat",\n      "value": "jsonex"\n    },\n    {\n      "name": "svCurrentCompany",\n      "value": "Bhrama Enterprises"\n    },\n    {\n      "name": "svFromDate",\n      "value": "20250401"\n    },\n    {\n      "name": "svToDate",\n      "value": "20260331"\n    }\n  ]\n}',
      XML: '<ENVELOPE>\n  <HEADER>\n    <VERSION>1</VERSION>\n    <TALLYREQUEST>Export</TALLYREQUEST>\n    <TYPE>Data</TYPE>\n    <ID>Sales Register</ID>\n  </HEADER>\n  <BODY>\n    <DESC>\n      <STATICVARIABLES>\n        <SVEXPORTFORMAT>XML</SVEXPORTFORMAT>\n        <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>\n        <SVFROMDATE>20250401</SVFROMDATE>\n        <SVTODATE>20260331</SVTODATE>\n      </STATICVARIABLES>\n    </DESC>\n  </BODY>\n</ENVELOPE>',
    },
    "pull-sales-register-plain": {
      JSON: '{\n  "static_variables": [\n    {\n      "name": "svExportFormat",\n      "value": "jsonex"\n    },\n    {\n      "name": "svCurrentCompany",\n      "value": "Bhrama Enterprises"\n    },\n    {\n      "name": "svFromDate",\n      "value": "20250401"\n    },\n    {\n      "name": "svToDate",\n      "value": "20260331"\n    }\n  ],\n  "tdlmessage": [\n    {\n      "definitions": [\n        {\n          "metadata": {\n            "name": "Sales Register",\n            "type": "Report",\n            "ismodify": true\n          },\n          "attributes": [\n            {\n              "Plain Xml": "Yes"\n            }\n          ]\n        }\n      ]\n    }\n  ]\n}',
      XML: '<ENVELOPE>\n  <HEADER>\n    <VERSION>1</VERSION>\n    <TALLYREQUEST>Export</TALLYREQUEST>\n    <TYPE>Data</TYPE>\n    <ID>Sales Register</ID>\n  </HEADER>\n  <BODY>\n    <DESC>\n      <STATICVARIABLES>\n        <SVEXPORTFORMAT>XML</SVEXPORTFORMAT>\n        <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>\n        <SVFROMDATE>20250401</SVFROMDATE>\n        <SVTODATE>20260331</SVTODATE>\n      </STATICVARIABLES>\n      <TDL>\n        <TDLMESSAGE>\n          <REPORT NAME="Sales Register" ISMODIFY="Yes" ISFIXED="No" ISINITIALIZE="No" ISOPTION="No" ISINTERNAL="No">\n            <PLAINXML>Yes</PLAINXML>\n          </REPORT>\n        </TDLMESSAGE>\n      </TDL>\n    </DESC>\n  </BODY>\n</ENVELOPE>',
    },
    "pull-sales-register-empty-fields": {
      JSON: '{\n  "static_variables": [\n    {\n      "name": "svExportFormat",\n      "value": "jsonex"\n    },\n    {\n      "name": "svCurrentCompany",\n      "value": "Bhrama Enterprises"\n    },\n    {\n      "name": "svFromDate",\n      "value": "20250401"\n    },\n    {\n      "name": "svToDate",\n      "value": "20260331"\n    }\n  ],\n  "tdlmessage": [\n    {\n      "definitions": [\n        {\n          "metadata": {\n            "name": "Sales Register",\n            "type": "Report",\n            "ismodify": true\n          },\n          "attributes": [\n            {\n              "Export Empty Fields": "Yes"\n            }\n          ]\n        }\n      ]\n    }\n  ]\n}',
      XML: '<ENVELOPE>\n  <HEADER>\n    <VERSION>1</VERSION>\n    <TALLYREQUEST>Export</TALLYREQUEST>\n    <TYPE>Data</TYPE>\n    <ID>Sales Register</ID>\n  </HEADER>\n  <BODY>\n    <DESC>\n      <STATICVARIABLES>\n        <SVEXPORTFORMAT>XML</SVEXPORTFORMAT>\n        <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>\n        <SVFROMDATE>20250401</SVFROMDATE>\n        <SVTODATE>20260331</SVTODATE>\n      </STATICVARIABLES>\n    </DESC>\n  </BODY>\n</ENVELOPE>',
    },
  };

  function mergePayloadsFromDom() {
    $(".contentSection").each(function () {
      var sid = $(this).attr("id");
      var $rb = $(this).find('[data-id="requestBody"]');
      if (!sid || !$rb.length) return;
      if (!REQUEST_PAYLOADS[sid]) {
        REQUEST_PAYLOADS[sid] = {
          JSON: $rb.val(),
          XML: GENERIC_XML_SAMPLE,
        };
      }
    });
  }

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function escapeAttr(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/"/g, "&quot;")
      .replace(/</g, "&lt;");
  }

  /** Mandatory headers: name is plain text (not editable); value is editable. */
  function fixedHeaderRow(name, value) {
    return (
      '<tr data-header-fixed="1">' +
      '<td class="align-middle small fw-semibold text-dark bg-light" style="width:38%">' +
      escapeHtml(name) +
      "</td>" +
      '<td><input type="text" class="form-control py-2" value="' +
      escapeAttr(value) +
      '"></td>' +
      "</tr>"
    );
  }

  /* Per-entity HTTP header definitions
   *
   *  Each key below maps a tab-id (or a tab-id prefix) to the fixed
   *  header rows that should appear in that tab's HTTP Headers table.
   *
   *  To update headers for a specific entity, find the matching comment
   *  block below and replace the fixedHeaderRow("key", "value") calls.
   *
   *  Row format:  fixedHeaderRow("header-name", "default-value")
   *
   * */
  var TAB_HEADERS = {
    /* LEDGER — one header set per API (tab id = key) */
    "create-ledger": [
      fixedHeaderRow("content-type", "application/json"),
      fixedHeaderRow("version", "1"),
      fixedHeaderRow("tallyrequest", "import"),
      fixedHeaderRow("type", "data"),
      fixedHeaderRow("id", "All Masters"),
    ],
    "alter-ledger": [
      fixedHeaderRow("content-type", "application/json"),
      fixedHeaderRow("version", "1"),
      fixedHeaderRow("tallyrequest", "import"),
      fixedHeaderRow("type", "data"),
      fixedHeaderRow("id", "All Masters"),
    ],
    "delete-ledger": [
      fixedHeaderRow("content-type", "application/json"),
      fixedHeaderRow("version", "1"),
      fixedHeaderRow("tallyrequest", "import"),
      fixedHeaderRow("type", "data"),
      fixedHeaderRow("id", "All Masters"),
    ],
    "pull-a-ledger": [
      fixedHeaderRow("content-type", "application/json"),
      fixedHeaderRow("version", "1"),
      fixedHeaderRow("tallyrequest", "export"),
      fixedHeaderRow("type", "object"),
      fixedHeaderRow("subtype", "Ledger"),
      fixedHeaderRow("id", "Kotak Bank"),
    ],
    "pull-all-ledger": [
      fixedHeaderRow("content-type", "application/json"),
      fixedHeaderRow("version", "1"),
      fixedHeaderRow("tallyrequest", "export"),
      fixedHeaderRow("type", "collection"),
      fixedHeaderRow("id", "Ledger"),
    ],
    "pull-ledgers-of-group": [
      fixedHeaderRow("content-type", "application/json"),
      fixedHeaderRow("version", "1"),
      fixedHeaderRow("tallyrequest", "export"),
      fixedHeaderRow("type", "collection"),
      fixedHeaderRow("id", "TSPLBankLedgers"),
    ],

    /* GROUP — one header set per API */
    "create-group": [
      fixedHeaderRow("content-type", "application/json"),
      fixedHeaderRow("version", "1"),
      fixedHeaderRow("tallyrequest", "import"),
      fixedHeaderRow("type", "data"),
      fixedHeaderRow("id", "All Masters"),
    ],
    "alter-group": [
      fixedHeaderRow("content-type", "application/json"),
      fixedHeaderRow("version", "1"),
      fixedHeaderRow("tallyrequest", "import"),
      fixedHeaderRow("type", "data"),
      fixedHeaderRow("id", "All Masters"),
    ],
    "delete-group": [
      fixedHeaderRow("content-type", "application/json"),
      fixedHeaderRow("version", "1"),
      fixedHeaderRow("tallyrequest", "import"),
      fixedHeaderRow("type", "data"),
      fixedHeaderRow("id", "All Masters"),
    ],
    "pull-group": [
      fixedHeaderRow("content-type", "application/json"),
      fixedHeaderRow("version", "1"),
      fixedHeaderRow("tallyrequest", "export"),
      fixedHeaderRow("type", "object"),
      fixedHeaderRow("subtype", "Group"),
      fixedHeaderRow("id", "Bank Accounts"),
    ],
    "pull-all-groups": [
      fixedHeaderRow("content-type", "application/json"),
      fixedHeaderRow("version", "1"),
      fixedHeaderRow("tallyrequest", "export"),
      fixedHeaderRow("type", "collection"),
      fixedHeaderRow("id", "Group"),
    ],
    "pull-groups-of-group": [
      fixedHeaderRow("content-type", "application/json"),
      fixedHeaderRow("version", "1"),
      fixedHeaderRow("tallyrequest", "export"),
      fixedHeaderRow("type", "collection"),
      fixedHeaderRow("id", "TSPLAssetGroups"),
    ],

    /* STOCK ITEM — one header set per API */
    "create-stock-item": [
      fixedHeaderRow("content-type", "application/json"),
      fixedHeaderRow("version", "1"),
      fixedHeaderRow("tallyrequest", "import"),
      fixedHeaderRow("type", "data"),
      fixedHeaderRow("id", "All Masters"),
    ],
    "alter-stock-item": [
      fixedHeaderRow("content-type", "application/json"),
      fixedHeaderRow("version", "1"),
      fixedHeaderRow("tallyrequest", "import"),
      fixedHeaderRow("type", "data"),
      fixedHeaderRow("id", "All Masters"),
    ],
    "delete-stock-item": [
      fixedHeaderRow("content-type", "application/json"),
      fixedHeaderRow("version", "1"),
      fixedHeaderRow("tallyrequest", "import"),
      fixedHeaderRow("type", "data"),
      fixedHeaderRow("id", "All Masters"),
    ],
    "pull-stock-item": [
      fixedHeaderRow("content-type", "application/json"),
      fixedHeaderRow("version", "1"),
      fixedHeaderRow("tallyrequest", "export"),
      fixedHeaderRow("type", "object"),
      fixedHeaderRow("subtype", "StockItem"),
      fixedHeaderRow("id", "Coffee Powder"),
    ],
    "pull-all-stock-items": [
      fixedHeaderRow("content-type", "application/json"),
      fixedHeaderRow("version", "1"),
      fixedHeaderRow("tallyrequest", "export"),
      fixedHeaderRow("type", "collection"),
      fixedHeaderRow("id", "Stock Item"),
    ],
    "pull-stock-items-of-stock-group": [
      fixedHeaderRow("content-type", "application/json"),
      fixedHeaderRow("version", "1"),
      fixedHeaderRow("tallyrequest", "export"),
      fixedHeaderRow("type", "collection"),
      fixedHeaderRow("id", "TSPLStockOfGroup "),
    ],

    /* STOCK GROUP — one header set per API */
    "create-stock-group": [
      fixedHeaderRow("content-type", "application/json"),
      fixedHeaderRow("version", "1"),
      fixedHeaderRow("tallyrequest", "import"),
      fixedHeaderRow("type", "data"),
      fixedHeaderRow("id", "All Masters"),
    ],
    "alter-stock-group": [
      fixedHeaderRow("content-type", "application/json"),
      fixedHeaderRow("version", "1"),
      fixedHeaderRow("tallyrequest", "import"),
      fixedHeaderRow("type", "data"),
      fixedHeaderRow("id", "All Masters"),
    ],
    "delete-stock-group": [
      fixedHeaderRow("content-type", "application/json"),
      fixedHeaderRow("version", "1"),
      fixedHeaderRow("tallyrequest", "import"),
      fixedHeaderRow("type", "data"),
      fixedHeaderRow("id", "All Masters"),
    ],
    "pull-stock-group": [
      fixedHeaderRow("content-type", "application/json"),
      fixedHeaderRow("version", "1"),
      fixedHeaderRow("tallyrequest", "export"),
      fixedHeaderRow("type", "object"),
      fixedHeaderRow("subtype", "Stock Group"),
      fixedHeaderRow("id", "Laptops"),
    ],
    "pull-all-stock-groups": [
      fixedHeaderRow("content-type", "application/json"),
      fixedHeaderRow("version", "1"),
      fixedHeaderRow("tallyrequest", "export"),
      fixedHeaderRow("type", "collection"),
      fixedHeaderRow("id", "Stock Group"),
    ],
    "pull-stock-group-zero-balance": [
      fixedHeaderRow("content-type", "application/json"),
      fixedHeaderRow("version", "1"),
      fixedHeaderRow("tallyrequest", "export"),
      fixedHeaderRow("type", "collection"),
      fixedHeaderRow("id", "TSPL Stock Group ZeroBal"),
    ],

    /* UNITS — one header set per API */
    "create-simple-unit": [
      fixedHeaderRow("content-type", "application/json"),
      fixedHeaderRow("version", "1"),
      fixedHeaderRow("tallyrequest", "import"),
      fixedHeaderRow("type", "data"),
      fixedHeaderRow("id", "All Masters"),
    ],
    "create-compound-unit": [
      fixedHeaderRow("content-type", "application/json"),
      fixedHeaderRow("version", "1"),
      fixedHeaderRow("tallyrequest", "import"),
      fixedHeaderRow("type", "data"),
      fixedHeaderRow("id", "All Masters"),
    ],
    "alter-unit": [
      fixedHeaderRow("content-type", "application/json"),
      fixedHeaderRow("version", "1"),
      fixedHeaderRow("tallyrequest", "import"),
      fixedHeaderRow("type", "data"),
      fixedHeaderRow("id", "All Masters"),
    ],
    "delete-unit": [
      fixedHeaderRow("content-type", "application/json"),
      fixedHeaderRow("version", "1"),
      fixedHeaderRow("tallyrequest", "import"),
      fixedHeaderRow("type", "data"),
      fixedHeaderRow("id", "All Masters"),
    ],
    "pull-unit": [
      fixedHeaderRow("content-type", "application/json"),
      fixedHeaderRow("version", "1"),
      fixedHeaderRow("tallyrequest", "export"),
      fixedHeaderRow("type", "object"),
      fixedHeaderRow("subtype", "Unit"),
      fixedHeaderRow("id", "Nos"),
    ],
    "pull-all-units": [
      fixedHeaderRow("content-type", "application/json"),
      fixedHeaderRow("version", "1"),
      fixedHeaderRow("tallyrequest", "export"),
      fixedHeaderRow("type", "collection"),
      fixedHeaderRow("id", "Unit"),
    ],

    /* PAYMENT — one header set per API */
    "payment-create-banking": [
      fixedHeaderRow("content-type", "application/json"),
      fixedHeaderRow("version", "1"),
      fixedHeaderRow("tallyrequest", "import"),
      fixedHeaderRow("type", "data"),
      fixedHeaderRow("id", "Vouchers"),
    ],
    "payment-create-cash": [
      fixedHeaderRow("content-type", "application/json"),
      fixedHeaderRow("version", "1"),
      fixedHeaderRow("tallyrequest", "import"),
      fixedHeaderRow("type", "data"),
      fixedHeaderRow("id", "Vouchers"),
    ],
    "payment-alter": [
      fixedHeaderRow("content-type", "application/json"),
      fixedHeaderRow("version", "1"),
      fixedHeaderRow("tallyrequest", "import"),
      fixedHeaderRow("type", "data"),
      fixedHeaderRow("id", "Vouchers"),
    ],
    "payment-delete": [
      fixedHeaderRow("content-type", "application/json"),
      fixedHeaderRow("version", "1"),
      fixedHeaderRow("tallyrequest", "import"),
      fixedHeaderRow("type", "data"),
      fixedHeaderRow("id", "Vouchers"),
    ],
    "payment-pull-all": [
      fixedHeaderRow("content-type", "application/json"),
      fixedHeaderRow("version", "1"),
      fixedHeaderRow("tallyrequest", "export"),
      fixedHeaderRow("type", "collection"),
      fixedHeaderRow("id", "TSPLAllPaymentVouchers"),
    ],
    "payment-pull-period": [
      fixedHeaderRow("content-type", "application/json"),
      fixedHeaderRow("version", "1"),
      fixedHeaderRow("tallyrequest", "export"),
      fixedHeaderRow("type", "collection"),
      fixedHeaderRow("id", "TSPLPaymentVouchers"),
    ],

    /* RECEIPT — one header set per API */
    "receipt-create": [
      fixedHeaderRow("content-type", "application/json"),
      fixedHeaderRow("version", "1"),
      fixedHeaderRow("tallyrequest", "import"),
      fixedHeaderRow("type", "data"),
      fixedHeaderRow("id", "Vouchers"),
    ],
    "receipt-create-cash": [
      fixedHeaderRow("content-type", "application/json"),
      fixedHeaderRow("version", "1"),
      fixedHeaderRow("tallyrequest", "import"),
      fixedHeaderRow("type", "data"),
      fixedHeaderRow("id", "Vouchers"),
    ],
    "receipt-alter": [
      fixedHeaderRow("content-type", "application/json"),
      fixedHeaderRow("version", "1"),
      fixedHeaderRow("tallyrequest", "import"),
      fixedHeaderRow("type", "data"),
      fixedHeaderRow("id", "Vouchers"),
    ],
    "receipt-delete": [
      fixedHeaderRow("content-type", "application/json"),
      fixedHeaderRow("version", "1"),
      fixedHeaderRow("tallyrequest", "import"),
      fixedHeaderRow("type", "data"),
      fixedHeaderRow("id", "Vouchers"),
    ],
    "receipt-pull-all": [
      fixedHeaderRow("content-type", "application/json"),
      fixedHeaderRow("version", "1"),
      fixedHeaderRow("tallyrequest", "export"),
      fixedHeaderRow("type", "collection"),
      fixedHeaderRow("id", "TSPL All Receipt Vouchers"),
    ],
    "receipt-pull-period": [
      fixedHeaderRow("content-type", "application/json"),
      fixedHeaderRow("version", "1"),
      fixedHeaderRow("tallyrequest", "export"),
      fixedHeaderRow("type", "collection"),
      fixedHeaderRow("id", "TSPL Receipt Vouchers"),
    ],

    /* SALES — one header set per API */
    "sales-create-item": [
      fixedHeaderRow("content-type", "application/json"),
      fixedHeaderRow("version", "1"),
      fixedHeaderRow("tallyrequest", "import"),
      fixedHeaderRow("type", "data"),
      fixedHeaderRow("id", "Vouchers"),
    ],
    "sales-create-gst": [
      fixedHeaderRow("content-type", "application/json"),
      fixedHeaderRow("version", "1"),
      fixedHeaderRow("tallyrequest", "import"),
      fixedHeaderRow("type", "data"),
      fixedHeaderRow("id", "Vouchers"),
    ],
    "sales-alter": [
      fixedHeaderRow("content-type", "application/json"),
      fixedHeaderRow("version", "1"),
      fixedHeaderRow("tallyrequest", "import"),
      fixedHeaderRow("type", "data"),
      fixedHeaderRow("id", "Vouchers"),
    ],
    "sales-delete": [
      fixedHeaderRow("content-type", "application/json"),
      fixedHeaderRow("version", "1"),
      fixedHeaderRow("tallyrequest", "import"),
      fixedHeaderRow("type", "data"),
      fixedHeaderRow("id", "Vouchers"),
    ],
    "sales-pull-all": [
      fixedHeaderRow("content-type", "application/json"),
      fixedHeaderRow("version", "1"),
      fixedHeaderRow("tallyrequest", "export"),
      fixedHeaderRow("type", "collection"),
      fixedHeaderRow("id", "TSPLAllSalesVouchers"),
    ],
    "sales-pull-period": [
      fixedHeaderRow("content-type", "application/json"),
      fixedHeaderRow("version", "1"),
      fixedHeaderRow("tallyrequest", "export"),
      fixedHeaderRow("type", "collection"),
      fixedHeaderRow("id", "TSPLSalesVouchers"),
    ],

    /* PURCHASE — one header set per API */
    "purchase-create-item": [
      fixedHeaderRow("content-type", "application/json"),
      fixedHeaderRow("version", "1"),
      fixedHeaderRow("tallyrequest", "import"),
      fixedHeaderRow("type", "data"),
      fixedHeaderRow("id", "Vouchers"),
    ],
    "purchase-create-gst": [
      fixedHeaderRow("content-type", "application/json"),
      fixedHeaderRow("version", "1"),
      fixedHeaderRow("tallyrequest", "import"),
      fixedHeaderRow("type", "data"),
      fixedHeaderRow("id", "Vouchers"),
    ],
    "purchase-alter": [
      fixedHeaderRow("content-type", "application/json"),
      fixedHeaderRow("version", "1"),
      fixedHeaderRow("tallyrequest", "import"),
      fixedHeaderRow("type", "data"),
      fixedHeaderRow("id", "Vouchers"),
    ],
    "purchase-delete": [
      fixedHeaderRow("content-type", "application/json"),
      fixedHeaderRow("version", "1"),
      fixedHeaderRow("tallyrequest", "import"),
      fixedHeaderRow("type", "data"),
      fixedHeaderRow("id", "Vouchers"),
    ],
    "purchase-pull-all": [
      fixedHeaderRow("content-type", "application/json"),
      fixedHeaderRow("version", "1"),
      fixedHeaderRow("tallyrequest", "export"),
      fixedHeaderRow("type", "collection"),
      fixedHeaderRow("id", "TSPL All Purchase Vouchers"),
    ],
    "purchase-pull-period": [
      fixedHeaderRow("content-type", "application/json"),
      fixedHeaderRow("version", "1"),
      fixedHeaderRow("tallyrequest", "export"),
      fixedHeaderRow("type", "collection"),
      fixedHeaderRow("id", "TSPL Purchase Vouchers"),
    ],

    /* Reports — Trial Balance */
    "pull-trial-balance-period": [
      fixedHeaderRow("content-type", "application/json"),
      fixedHeaderRow("version", "1"),
      fixedHeaderRow("tallyrequest", "export"),
      fixedHeaderRow("type", "data"),
      fixedHeaderRow("id", "Trial Balance"),
    ],
    /* Reports — Trial Balance Detailed */
    "pull-trial-balance-detailed": [
      fixedHeaderRow("content-type", "application/json"),
      fixedHeaderRow("version", "1"),
      fixedHeaderRow("tallyrequest", "export"),
      fixedHeaderRow("type", "data"),
      fixedHeaderRow("id", "Trial Balance"),
    ],

    /* DEFAULT fallback (any tab not matched above) */
    default: [
      fixedHeaderRow("content-type", "application/json"),
      fixedHeaderRow("method", "export"),
      fixedHeaderRow("tallyrequest", "export"),
      fixedHeaderRow("type", "collection"),
      fixedHeaderRow("id", "ledger"),
    ],

    /* Reports — Trial Balance Plain Format */
    "pull-trial-balance-plain": [
      fixedHeaderRow("content-type", "application/json"),
      fixedHeaderRow("version", "1"),
      fixedHeaderRow("tallyrequest", "export"),
      fixedHeaderRow("type", "data"),
      fixedHeaderRow("id", "Trial Balance"),
    ],
    /* Reports — Trial Balance with Empty Fields */
    "pull-trial-balance-empty-fields": [
      fixedHeaderRow("content-type", "application/json"),
      fixedHeaderRow("version", "1"),
      fixedHeaderRow("tallyrequest", "export"),
      fixedHeaderRow("type", "data"),
      fixedHeaderRow("id", "Trial Balance"),
    ],
    /* Reports — Trial Balance Ledger wise */
    "pull-trial-balance-ledger-wise": [
      fixedHeaderRow("content-type", "application/json"),
      fixedHeaderRow("version", "1"),
      fixedHeaderRow("tallyrequest", "export"),
      fixedHeaderRow("type", "data"),
      fixedHeaderRow("id", "Trial Balance"),
    ],
    /* Reports — Trial Balance for a Group */
    "pull-trial-balance-group": [
      fixedHeaderRow("content-type", "application/json"),
      fixedHeaderRow("version", "1"),
      fixedHeaderRow("tallyrequest", "export"),
      fixedHeaderRow("type", "data"),
      fixedHeaderRow("id", "Trial Balance"),
    ],
    /* Reports — Sales Register */
    "pull-sales-register-period": [
      fixedHeaderRow("content-type", "application/json"),
      fixedHeaderRow("version", "1"),
      fixedHeaderRow("tallyrequest", "export"),
      fixedHeaderRow("type", "data"),
      fixedHeaderRow("id", "Sales Register"),
    ],
    /* Reports — Sales Register Plain Format */
    "pull-sales-register-plain": [
      fixedHeaderRow("content-type", "application/json"),
      fixedHeaderRow("version", "1"),
      fixedHeaderRow("tallyrequest", "export"),
      fixedHeaderRow("type", "data"),
      fixedHeaderRow("id", "Sales Register"),
    ],
    /* Reports — Sales Register with Empty Fields */
    "pull-sales-register-empty-fields": [
      fixedHeaderRow("content-type", "application/json"),
      fixedHeaderRow("version", "1"),
      fixedHeaderRow("tallyrequest", "export"),
      fixedHeaderRow("type", "data"),
      fixedHeaderRow("id", "Sales Register"),
    ],
  }; /* end http_HEADERS */

  /** Resolve which header-set key applies to a given tab id (exact tab id only). */
  function resolveHeaderKey(tabId) {
    if (!tabId) return "default";
    if (TAB_HEADERS[tabId]) return tabId;
    return "default";
  }

  function headersWrapHtml(tabId) {
    var key = resolveHeaderKey(tabId);
    var rows = TAB_HEADERS[key] || TAB_HEADERS["default"];
    return (
      '<div class="mb-4 tally-http-headers-wrap">' +
      '<div class="d-flex justify-content-between align-items-center bg-primary bg-dark-yellow text-white px-3 py-3 rounded-top">' +
      '<span class="small fw-bold">HTTP Headers</span>' +
      '<button type="button" class="btn btn-light btn-sm py-1" data-id="addHeaderBtn">Add header</button>' +
      "</div>" +
      '<div class="table-responsive border border-top-0 rounded-bottom">' +
      '<table class="table table-bordered headers-table mb-0">' +
      '<thead class="table-light"><tr><th style="width:38%">Header</th><th>Value</th></tr></thead>' +
      "<tbody>" +
      rows.join("") +
      "</tbody></table></div></div>"
    );
  }

  /** @param {JQuery} [$root] - optional .contentSection; if omitted, all .page-body in the document */
  function injectHeadersTables($root) {
    var $scope =
      $root && $root.length ? $root.find(".page-body") : $(".page-body");
    $scope.each(function () {
      var $pb = $(this);
      if (!$pb.find('[data-id="sendRequestBtn"]').length) return;
      $pb.find(".tally-http-headers-wrap").remove();
      $pb.find(".headers-table").closest(".mb-4").remove();
      var $anchor = $pb.find(".row.g-4.mb-4").first();
      if (!$anchor.length) return;
      var tabId =
        $pb.attr("id") || $pb.closest(".contentSection").attr("id") || "";
      $anchor.before(headersWrapHtml(tabId));
    });
  }

  function resetTemplate($page) {
    var tabId = $page.attr("id");
    var format = ($page.find('[data-id="payloadFormat"]').val() || "JSON")
      .toString()
      .trim();
    var $rb = $page.find('[data-id="requestBody"]');
    if (!$rb.length) {
      $page.find('[data-id="responseBody"]').val("");
      tcApplyDisplayRequestUrl($page);
      return;
    }
    var pack = REQUEST_PAYLOADS[tabId];
    if (pack && pack[format]) {
      $rb.val(pack[format]);
    } else if (format === "XML") {
      $rb.val(GENERIC_XML_SAMPLE);
    } else if (pack && pack.JSON) {
      $rb.val(pack.JSON);
    } else {
      $rb.val("{}");
    }
    $page.find('[data-id="responseBody"]').val("");
    tcApplyDisplayRequestUrl($page);
    injectHeadersTables($page);
    var $pbReset = $page.find(".page-body").first();
    if ($pbReset.length) {
      setHeadersVisibility($pbReset, format);
      syncContentTypeHeader($pbReset, format);
    } else {
      setHeadersVisibility($page, format);
      syncContentTypeHeader($page, format);
    }
  }

  function setHeadersVisibility($page, fmt) {
    $page
      .find(".tally-http-headers-wrap")
      .toggleClass("d-none", fmt !== "JSON");
  }

  function syncContentTypeHeader($page, fmt) {
    if (fmt !== "JSON") return;
    $page.find(".headers-table tbody tr").each(function () {
      var $cells = $(this).find("td");
      if ($cells.length < 2) return;
      var $nameInp = $cells.eq(0).find("input");
      var name = $nameInp.length
        ? $nameInp.val().trim()
        : $cells.eq(0).text().trim();
      if (name.toLowerCase() === "content-type") {
        var $inp = $cells.eq(1).find("input");
        if ($inp.length) {
          $inp.val("application/json");
        }
      }
    });
  }

  $(document).on("click", '[data-id="addHeaderBtn"]', function () {
    var $tbody = $(this)
      .closest(".tally-http-headers-wrap")
      .find(".headers-table tbody");
    var row =
      "<tr>" +
      '<td><input type="text" class="form-control form-control-sm" placeholder="Header name"></td>' +
      "<td>" +
      '<div class="input-group input-group-sm">' +
      '<input type="text" class="form-control py-2" placeholder="Value">' +
      '<button type="button" class="btn btn-outline-danger" data-id="removeHeaderBtn" title="Remove header"><i class="bi bi-x-lg"></i></button>' +
      "</div>" +
      "</td>" +
      "</tr>";
    $tbody.append(row);
  });

  $(document).on("click", '[data-id="removeHeaderBtn"]', function () {
    var $tr = $(this).closest("tr");
    if ($tr.is("[data-header-fixed]")) return;
    $tr.remove();
  });

  $(document).on("click", '[data-id="loadBtn"]', function () {
    var $page = $(this).closest(".contentSection");
    tcRememberRequestUrl($page.find('[data-id="requestUrl"]').val());
    resetTemplate($page);
    var $pb = $page.find(".page-body").first();
    if ($pb.length) tcHidePageStatusAlert($pb);
  });

  $(document).on("input change", '[data-id="requestUrl"]', function () {
    tcRememberRequestUrl($(this).val());
    tcSetRequestUrlFieldState($(this));
  });

  $(document).on("change", '[data-id="payloadFormat"]', function () {
    tcSessionPayloadFormat = tcNormalizePayloadFormat($(this).val());
    var $section = $(this).closest(".contentSection");
    tcRememberRequestUrl($section.find('[data-id="requestUrl"]').val());
    resetTemplate($section);
    tcSyncHotBlocks($section, tcSessionPayloadFormat);
    var $pbFmt = $section.find(".page-body").first();
    if ($pbFmt.length) tcHidePageStatusAlert($pbFmt);
  });

  injectHeadersTables();

  mergePayloadsFromDom();

  // Initial setup for the placeholder (the loaded page handles this now)
  // (Nothing needed initially as the first fetch takes over)

  function tcCollectHeaders($page) {
    var fmt = ($page.find('[data-id="payloadFormat"]').val() || "JSON")
      .toString()
      .trim();
    if (
      fmt !== "JSON" ||
      $page.find(".tally-http-headers-wrap").hasClass("d-none")
    ) {
      return {};
    }
    var headers = {};
    $page.find(".headers-table tbody tr").each(function () {
      var $cells = $(this).find("td");
      if ($cells.length < 2) return;
      var $nameInp = $cells.eq(0).find("input");
      var name = (
        $nameInp.length ? $nameInp.val() : $cells.eq(0).text()
      ).trim();
      var $valInp = $cells.eq(1).find("input");
      var val = $valInp.length
        ? String($valInp.val()).trim()
        : $cells.eq(1).text().trim();
      if (name) headers[name] = val;
    });
    return headers;
  }

  function tcFormatResponseBody(text, contentType) {
    var ct = (contentType || "").toLowerCase();
    var t = (text || "").trim();
    if (
      ct.indexOf("json") >= 0 ||
      t.startsWith("{") ||
      t.startsWith("[")
    ) {
      try {
        // Keep the response body exactly as received for JSON payloads.
        return text;
        // return JSON.stringify(JSON.parse(text), null, 2);
        /* Above Beautification line commented for testing */
      } catch (e) {
        /* fall through */
      }
    }
    // Strip blank lines from XML responses (Tally returns XML with \r\n\r\n between tags).
    // Replace two or more consecutive newlines (with optional whitespace) with a single newline.
    return t.replace(/(\r?\n[ \t]*){2,}/g, "\n");
  }

  function tcDownload(filename, text) {
    var blob = new Blob([text != null ? text : ""], {
      type: "text/plain;charset=utf-8",
    });
    var a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(a.href);
  }

  $(document).on("click", '[data-id="sendRequestBtn"]', function () {
    var $page = $(this).closest(".page-body");
    if (!$page.length) return;

    var urlDisplay = (
      $page.find('[data-id="requestUrl"]').val() || ""
    ).trim();
    tcRememberRequestUrl(urlDisplay);
    var url = tcProxyRequestUrl(urlDisplay);
    var body = $page.find('[data-id="requestBody"]').val() || "";
    var $response = $page.find('[data-id="responseBody"]');
    var format = ($page.find('[data-id="payloadFormat"]').val() || "JSON")
      .toString()
      .trim();
    var $sendAlert = $page.find(".container-fluid.py-4 .alert").first();

    function setSendAlert(ok, message) {
      if (!$sendAlert.length) return;
      $sendAlert.removeClass("d-none");
      $sendAlert.removeClass("alert-success alert-danger alert-warning");
      $sendAlert.addClass(ok ? "alert-success" : "alert-danger");
      $sendAlert.text(message);
    }

    var urlCheck = tcValidateRequestUrl(urlDisplay);
    tcSetRequestUrlFieldState($page.find('[data-id="requestUrl"]'), urlCheck);
    if (!urlCheck.valid) {
      $response.val("Error: " + urlCheck.message);
      setSendAlert(false, urlCheck.message);
      return;
    }

    var headers = tcCollectHeaders($page);
    if (format === "JSON") {
      var hasCT = Object.keys(headers).some(function (k) {
        return k.toLowerCase() === "content-type";
      });
      if (!hasCT) {
        headers["Content-Type"] = "application/json; charset=utf-8";
      }
    } else {
      headers = {};
    }

    $response.val("Sending request to TallyPrime...");

    var xhr = new XMLHttpRequest();
    xhr.open("POST", url, true);
    tcSetProxyPortHeader(xhr, urlDisplay);

    for (var key in headers) {
      if (headers.hasOwnProperty(key)) {
        xhr.setRequestHeader(key, headers[key]);
      }
    }

    xhr.onreadystatechange = function () {
      if (xhr.readyState === 4) {
        if (xhr.status === 0) {
          var msg =
            "Request failed (ERR_CONNECTION_RESET or Network Error)\n\n";
          msg += "--- Tips ---\n";
          msg +=
            " Start TallyPrime, load a company, and keep HTTP enabled (default port 9000).\n";
          msg +=
            " Check README.md to run Chrome with web-security disabled to bypass CORS errors.\n";
          $response.val(msg);
        } else {
          var ct = xhr.getResponseHeader("content-type") || "";
          var formatted = tcFormatResponseBody(xhr.responseText, ct);
          var out = "--- HTTP ---\n";
          out += "Status: " + xhr.status + " " + xhr.statusText + "\n";
          out += "content-type: " + (ct || "(none)") + "\n\n";
          out += "--- Body ---\n";
          out += formatted;
          $response.val(out);
          var ok = xhr.status >= 200 && xhr.status < 300;
          setSendAlert(ok, "HTTP " + xhr.status + " " + xhr.statusText);
        }
      }
    };

    xhr.onerror = function () {
      var msg =
        "Request failed (ERR_CONNECTION_RESET or Network Error)\n\n";
      msg += "--- Tips ---\n";
      msg +=
        "Start TallyPrime, load a company, and keep HTTP enabled (default port 9000).\n";
      msg +=
        "Check README.md to run Chrome with web-security disabled to bypass CORS errors.\n";
      $response.val(msg);
    };

    xhr.send(body);
  });

  $(document).on("click", '[data-id="validateBtn"]', function () {
    var $page = $(this).closest(".page-body");
    if (!$page.length) return;

    var urlDisplay = (
      $page.find('[data-id="requestUrl"]').val() || ""
    ).trim();
    tcRememberRequestUrl(urlDisplay);
    var url = tcProxyRequestUrl(urlDisplay);
    var tallyPort = tcTallyPortFromUrl(urlDisplay);
    var noCompanyMsg =
      "TallyPrime is running on port " +
      tallyPort +
      ". Load a company before sending data requests";
    var noConnectionMsg =
      "No Connection - Run TallyAPIConnectorV2.0.exe to establish connection with TallyPrime on port " +
      tallyPort;
    var $alert = $page.find(".container-fluid.py-4 .alert").first();

    function setAlert(ok, message) {
      if ($alert.length) {
        // Reveal the wrapper so its py-4 padding is restored alongside the alert
        $alert.closest(".container-fluid.py-4").removeClass("d-none");
        $alert.removeClass("d-none");
        $alert.removeClass("alert-success alert-danger alert-warning");
        $alert.addClass(ok ? "alert-success" : "alert-danger");
        $alert.text(message);
      } else {
        var $resp = $page.find('[data-id="responseBody"]');
        if ($resp.length) {
          $resp.val((ok ? "✓ " : "✗ ") + message);
        }
      }
    }

    var urlCheck = tcValidateRequestUrl(urlDisplay);
    tcSetRequestUrlFieldState($page.find('[data-id="requestUrl"]'), urlCheck);
    if (!urlCheck.valid) {
      setAlert(false, urlCheck.message);
      return;
    }

    var xhr = new XMLHttpRequest();
    xhr.open("POST", url, true);
    tcSetProxyPortHeader(xhr, urlDisplay);

    xhr.onreadystatechange = function () {
      if (xhr.readyState === 4) {
        if (xhr.status > 0) {
          //trim the response text from all the tags
          var responseText = xhr.responseText;
          responseText = responseText.replace(/<[^>]*>/g, "");

          //if the response is TallyPrime is running and a company is loaded
          if (responseText.includes("TallyPrime Server is Running")) {
            //make another fetch request to pull all stock groups with id as company check if the company is loaded or not by data.collection array value is more than 1
            var xhr2 = new XMLHttpRequest();
            var headers = {
              "content-type": "application/json",
              "version": "1",
              "tallyrequest": "export",
              "type": "collection",
              "id": "company",
              "x-tally-port": tallyPort
            };
            var body = {
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
            };
            xhr2.open("POST", url, true);
            for (var key in headers) {
              if (headers.hasOwnProperty(key)) {
                xhr2.setRequestHeader(key, headers[key]);
              }
            }
            xhr2.onreadystatechange = function () {
              if (xhr2.readyState === 4) {
                if (xhr2.status > 0) {
                  var jsonResponse = (xhr2.responseText || "").trim();
                  if (!jsonResponse) {
                    setAlert(false, noCompanyMsg);
                    return;
                  }
                  try {
                    var data = JSON.parse(jsonResponse);
                    var collection =
                      data && data.data ? data.data.collection : undefined;
                    var hasValues = false;
                    if (Array.isArray(collection)) {
                      hasValues = collection.length > 0;
                    } else if (collection && typeof collection === "object") {
                      hasValues = Object.keys(collection).length > 0;
                    } else if (collection) {
                      hasValues = true;
                    }

                    if (hasValues) {
                      setAlert(
                        true,
                        "TallyPrime is running on port " +
                          tallyPort +
                          " with company loaded",
                      );
                    } else {
                      setAlert(false, noCompanyMsg);
                    }
                  } catch (e) {
                    setAlert(false, noCompanyMsg);
                  }
                } else {
                  setAlert(false, noConnectionMsg);
                }
              }
            };
            xhr2.send(JSON.stringify(body));
          } else {
            setAlert(
              false,
              responseText
            );
          }
        } else {
          setAlert(false, noConnectionMsg);
        }
      }
    };

    xhr.onerror = function () {
      setAlert(false, noConnectionMsg);
    };

    xhr.send("");
  });

  $(document).on("click", '[data-id="downloadRequestBtn"]', function () {
    var $page = $(this).closest(".page-body");
    var headers = tcCollectHeaders($page);
    var body = $page.find('[data-id="requestBody"]').val() || "";
    var format = ($page.find('[data-id="payloadFormat"]').val() || "JSON").toString().trim();

    var output = "";
    if (format === "JSON") {
      var headerKeys = Object.keys(headers);
      if (headerKeys.length > 0) {
        for (var i = 0; i < headerKeys.length; i++) {
          output += headerKeys[i] + ": " + headers[headerKeys[i]] + "\n";
        }
        output += "\n";
      }
    }
    output += body;

    tcDownload(
      "tally-api-request.txt",
      output
    );
  });

  $(document).on("click", '[data-id="downloadResponseBtn"]', function () {
    var $page = $(this).closest(".page-body");
    tcDownload(
      "tally-api-response.txt",
      $page.find('[data-id="responseBody"]').val() || "",
    );
  });

  /* HANDS_ON_TASKS: per-tab, per-task, per-format code snippets */
  // var HANDS_ON_TASKS = {
  //   "create-ledger": {
  //     1: {
  //       JSON: '{\n  "static_variables": [\n    { "name": "svExportFormat", "value": "$$SysName:jsonex" },\n    { "name": "svCurrentCompany", "value": "Bhrama Enterprises" }\n  ],\n  "tallymessage": [\n    {\n      "ledger": {\n        "name": "SADE Pvt Ltd",\n        "parent": "Sundry Debtors",\n        "openingbalance": "0"\n      }\n    }\n  ]\n}',
  //       XML: '<ENVELOPE>\n    <HEADER>\n        <TALLYREQUEST>Import Data</TALLYREQUEST>\n    </HEADER>\n    <BODY>\n        <IMPORTDATA>\n            <REQUESTDESC>\n                <REPORTNAME>All Masters</REPORTNAME>\n            </REQUESTDESC>\n            <REQUESTDATA>\n                <TALLYMESSAGE>\n                    <LEDGER NAME=\"SADE Pvt Ltd\" ACTION=\"Create\">\n                        <PARENT>Sundry Debtors</PARENT>\n                        <OPENINGBALANCE>0</OPENINGBALANCE>\n                    </LEDGER>\n                </TALLYMESSAGE>\n            </REQUESTDATA>\n        </IMPORTDATA>\n    </BODY>\n</ENVELOPE>',
  //     },
  //     2: {
  //       JSON: '{\n  "static_variables": [\n    { "name": "svExportFormat", "value": "$$SysName:jsonex" },\n    { "name": "svCurrentCompany", "value": "Bhrama Enterprises" }\n  ],\n  "tallymessage": [\n    {\n      "ledger": {\n        "name": "Kotak Bank",\n        "parent": "Bank Accounts",\n        "openingbalance": "0"\n      }\n    }\n  ]\n}',
  //       XML: '<ENVELOPE>\n    <HEADER>\n        <TALLYREQUEST>Import Data</TALLYREQUEST>\n    </HEADER>\n    <BODY>\n        <IMPORTDATA>\n            <REQUESTDESC>\n                <REPORTNAME>All Masters</REPORTNAME>\n            </REQUESTDESC>\n            <REQUESTDATA>\n                <TALLYMESSAGE>\n                    <LEDGER NAME=\"Kotak Bank\" ACTION=\"Create\">\n                        <PARENT>Bank Accounts</PARENT>\n                        <OPENINGBALANCE>0</OPENINGBALANCE>\n                    </LEDGER>\n                </TALLYMESSAGE>\n            </REQUESTDATA>\n        </IMPORTDATA>\n    </BODY>\n</ENVELOPE>',
  //     },
  //   },
  //   "alter-ledger": {
  //     1: {
  //       JSON: '{\n  "static_variables": [\n    { "name": "svExportFormat", "value": "$$SysName:jsonex" },\n    { "name": "svCurrentCompany", "value": "Bhrama Enterprises" }\n  ],\n  "tallymessage": [\n    {\n      "ledger": {\n        "name": "SADE Pvt Ltd",\n        "action": "Alter",\n        "openingbalance": "75000"\n      }\n    }\n  ]\n}',
  //       XML: '<ENVELOPE>\n    <HEADER>\n        <TALLYREQUEST>Import Data</TALLYREQUEST>\n    </HEADER>\n    <BODY>\n        <IMPORTDATA>\n            <REQUESTDESC>\n                <REPORTNAME>All Masters</REPORTNAME>\n            </REQUESTDESC>\n            <REQUESTDATA>\n                <TALLYMESSAGE>\n                    <LEDGER NAME=\"SADE Pvt Ltd\" ACTION=\"Alter\">\n                        <OPENINGBALANCE>75000</OPENINGBALANCE>\n                    </LEDGER>\n                </TALLYMESSAGE>\n            </REQUESTDATA>\n        </IMPORTDATA>\n    </BODY>\n</ENVELOPE>',
  //     },
  //     2: {
  //       JSON: '{\n  "static_variables": [\n    { "name": "svExportFormat", "value": "$$SysName:jsonex" },\n    { "name": "svCurrentCompany", "value": "Bhrama Enterprises" }\n  ],\n  "tallymessage": [\n    {\n      "ledger": {\n        "name": "Kotak Bank",\n        "action": "Alter",\n        "parent": "Bank Accounts"\n      }\n    }\n  ]\n}',
  //       XML: '<ENVELOPE>\n    <HEADER>\n        <TALLYREQUEST>Import Data</TALLYREQUEST>\n    </HEADER>\n    <BODY>\n        <IMPORTDATA>\n            <REQUESTDESC>\n                <REPORTNAME>All Masters</REPORTNAME>\n            </REQUESTDESC>\n            <REQUESTDATA>\n                <TALLYMESSAGE>\n                    <LEDGER NAME=\"Kotak Bank\" ACTION=\"Alter\">\n                        <PARENT>Bank Accounts</PARENT>\n                    </LEDGER>\n                </TALLYMESSAGE>\n            </REQUESTDATA>\n        </IMPORTDATA>\n    </BODY>\n</ENVELOPE>',
  //     },
  //   },
  //   "delete-ledger": {
  //     1: {
  //       JSON: '{\n  "static_variables": [\n    { "name": "svExportFormat", "value": "$$SysName:jsonex" },\n    { "name": "svCurrentCompany", "value": "Bhrama Enterprises" }\n  ],\n  "tallymessage": [\n    {\n      "ledger": {\n        "name": "SADE Pvt Ltd",\n        "action": "Delete"\n      }\n    }\n  ]\n}',
  //       XML: '<ENVELOPE>\n    <HEADER>\n        <TALLYREQUEST>Import Data</TALLYREQUEST>\n    </HEADER>\n    <BODY>\n        <IMPORTDATA>\n            <REQUESTDESC>\n                <REPORTNAME>All Masters</REPORTNAME>\n            </REQUESTDESC>\n            <REQUESTDATA>\n                <TALLYMESSAGE>\n                    <LEDGER NAME=\"SADE Pvt Ltd\" ACTION=\"Delete\">\n                    </LEDGER>\n                </TALLYMESSAGE>\n            </REQUESTDATA>\n        </IMPORTDATA>\n    </BODY>\n</ENVELOPE>',
  //     },
  //   },
  //   "pull-a-ledger": {
  //     1: {
  //       JSON: '{\n  "static_variables": [\n    { "name": "svExportFormat", "value": "$$SysName:jsonex" },\n    { "name": "svCurrentCompany", "value": "Bhrama Enterprises" },\n    { "name": "LedgerName", "value": "Cash" }\n  ]\n}',
  //       XML: "<ENVELOPE>\n    <HEADER>\n        <TALLYREQUEST>Export Data</TALLYREQUEST>\n    </HEADER>\n    <BODY>\n        <EXPORTDATA>\n            <REQUESTDESC>\n                <REPORTNAME>Ledger</REPORTNAME>\n                <STATICVARIABLES>\n                    <LEDGERNAME>Cash</LEDGERNAME>\n                </STATICVARIABLES>\n            </REQUESTDESC>\n        </EXPORTDATA>\n    </BODY>\n</ENVELOPE>",
  //     },
  //   },
  // };

  /* Download Code button in Hands-on Testing */
  //   $(document).on("click", ".download-code-btn", function () {
  //     var $btn = $(this);
  //     var taskNum = parseInt($btn.attr("data-task") || "1", 10);
  //     var $section = $btn.closest(".contentSection");
  //     var tabId = $section.attr("id") || "";
  //     var fmt = ($section.find('[data-id="payloadFormat"]').val() || "JSON")
  //       .toString()
  //       .trim();
  //     var ext = fmt === "XML" ? "xml" : "json";
  //     var filename =
  //       tabId + "-task" + taskNum + "-" + fmt.toLowerCase() + "." + ext;

  //     var snippet = "";
  //     if (
  //       HANDS_ON_TASKS[tabId] &&
  //       HANDS_ON_TASKS[tabId][taskNum] &&
  //       HANDS_ON_TASKS[tabId][taskNum][fmt]
  //     ) {
  //       snippet = HANDS_ON_TASKS[tabId][taskNum][fmt];
  //     } else if (REQUEST_PAYLOADS[tabId] && REQUEST_PAYLOADS[tabId][fmt]) {
  //       snippet = REQUEST_PAYLOADS[tabId][fmt];
  //     } else {
  //       snippet = $section.find('[data-id="requestBody"]').val() || "";
  //     }

  //     tcDownload(filename, snippet);
  //   });
});

/* ── Dynamic Video Modal ──────────────────────────────────────────────
       *
       * To trigger this modal from ANY button/link, add:
       *   class="video-modal-trigger"
       *   data-video-url="https://www.youtube.com/embed/<VIDEO_ID>"
       *   data-video-title="Your Video Title"
       *
       * Example:
       *   <button
       *     class="btn btn-sm btn-outline-primary video-modal-trigger"
       *     data-video-url="https://www.youtube.com/embed/leyl5w8GAmo"
       *     data-video-title="Create a Group"
       *   >
       *     &#9654; Watch
       *   </button>
       * ─────────────────────────────────────────────────────────────────── */
$(function () {
  var modalEl = document.getElementById("videoModal");
  var iframe = document.getElementById("videoModalIframe");
  var bsModal = null;
  var pendingUrl = "";
  var pendingTitle = "";

  function getModal() {
    if (!bsModal) bsModal = new bootstrap.Modal(modalEl);
    return bsModal;
  }

  // Open: store url & title, then show modal
  // (iframe.src is set in shown.bs.modal — setting it on a hidden iframe
  //  causes browsers to block the load, producing the broken-image state)
  document.addEventListener("click", function (e) {
    var trigger = e.target.closest(".video-modal-trigger");
    if (!trigger) return;
    e.preventDefault();

    pendingUrl = trigger.getAttribute("data-video-url") || "";
    pendingTitle = trigger.getAttribute("data-video-title") || "";

    getModal().show();
  });

  // Set src only once the modal is fully visible
  modalEl.addEventListener("shown.bs.modal", function () {
    iframe.title = pendingTitle;
    iframe.src = pendingUrl;
  });

  // Close: clear src so the video stops playing
  modalEl.addEventListener("hide.bs.modal", function () {
    iframe.src = "";
    pendingUrl = "";
    pendingTitle = "";
  });
});
