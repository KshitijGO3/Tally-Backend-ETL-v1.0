
// Prevent multiple script executions
if (window.GA_TRACKING_INITIALIZED) {
    console.warn('GA Tracking: Script already initialized, skipping duplicate execution');
} else {
    window.GA_TRACKING_INITIALIZED = true;

    var productMap = "";
    var ProductNames = [];
    ProductNames['TE9'] = 'TallyPrime';
    ProductNames['EDIT_LOG'] = 'TallyPrime Edit Log';
    ProductNames['TE9_RENT'] = 'TallyPrime Rental';
    ProductNames['TS9'] = 'TallyPrime Server';
    ProductNames['TP_CLOUD'] = 'TallyPrime On AWS';
    ProductNames['TP_CLOUD_SERVER'] = 'TallyPrime Server On AWS';
    ProductNames['TDE'] = 'TallyPrime Developer';
    ProductNames['SHOPER_RENT'] = 'Shoper 9 Rental';
    var company = 'Tally Prime';
    var rentalDiscount = [];
    rentalDiscount['3'] = .05; // 5% discount for 3 months;   
    rentalDiscount['12'] = .1;// 10% discount for 12 months;
    var productData = [];

    async function setProductCookie() {
        try {
            // const productData = localStorage.getItem("productData"+window.TALLY_WEBSITE_COUNTRY_INITIAL) || '';
            // if (productData) return; 
            const host = window.location.host;

            if (!host) {
                console.warn('GA Tracking: Host not available, skipping product data fetch');
                return;
            }
            var strForCountry = [];
            strForCountry['IN'] = 1;
            strForCountry['MENA'] = 2;
            strForCountry['MENA-AR'] = 2;
            strForCountry['SSA'] = 4;
            strForCountry['BD'] = 3;
            strForCountry['BD-EN'] = 3;
            strForCountry['APAC'] = 2;
            strForCountry['US'] = 5;
            strForCountry['GLOBAL'] = 2;

            var strCountry = [];
            strCountry['IN'] = 1;
            strCountry['MENA'] = 5;
            strCountry['MENA-AR'] = 5;
            strCountry['SSA'] = 8;
            strCountry['BD'] = 6;
            strCountry['BD-EN'] = 6;
            strCountry['APAC'] = 7;
            strCountry['US'] = 14;
            strCountry['GLOBAL'] = 5;

            var strCurrencyID = [];
            strCurrencyID['IN'] = 1;
            strCurrencyID['MENA'] = 8;
            strCurrencyID['MENA-AR'] = 8;
            strCurrencyID['SSA'] = 9;
            strCurrencyID['BD'] = 2;
            strCurrencyID['BD-EN'] = 2;
            strCurrencyID['APAC'] = 23;
            strCurrencyID['US'] = 2;
            strCurrencyID['GLOBAL'] = 2;
            //return true to avoid this fetch call
            // return true;
            const response = await fetch(`https://${host}/wp-content/themes/tally/api/getPriceData_api.php?strForCountry=${strForCountry[window.TALLY_WEBSITE_COUNTRY_INITIAL]}&strCurrencyID=${strCurrencyID[window.TALLY_WEBSITE_COUNTRY_INITIAL]}&strCountry=${strCountry[window.TALLY_WEBSITE_COUNTRY_INITIAL]}`);

            if (!response.ok) {
                console.warn('GA Tracking: Failed to fetch product data:', response.status, response.statusText);
                return;
            }

            const data = await response.json();

            if (!data || typeof data !== 'object') {
                console.warn('GA Tracking: Invalid product data received');
                return;
            }

            productMap = data;
            const expires = new Date(Date.now() + 60 * 60 * 1000).toUTCString();
            // document.cookie = "productData=" + encodeURIComponent(JSON.stringify(productMap)) + "; path=/; expires=" + expires;
            // console.log(encodeURIComponent(JSON.stringify(productMap)));
            // console.log(JSON.stringify(productMap));
            // document.cookie = "productData=" + encodeURIComponent(JSON.stringify(productMap)) + "; expires=" + expires + "; path=/";

            // prepare a json array of product data with item id as key and product data as value
            try {
                for (const outerKey in data) {
                    if (data.hasOwnProperty(outerKey)) {
                        const innerObj = data[outerKey];
                        if (innerObj && typeof innerObj === 'object') {
                            for (const innerKey in innerObj) {
                                if (innerObj.hasOwnProperty(innerKey)) {
                                    const product = innerObj[innerKey];
                                    if (product && product.ITEM_ID) {
                                        productData[product.ITEM_ID] = product;
                                    }
                                }
                            }
                        }
                    }
                }
            } catch (parseError) {
                console.warn('GA Tracking: Error parsing product data:', parseError);
            }

            // try {
            //     ViewListEventPush();
            // } catch (viewListError) {
            //     console.warn('GA Tracking: Error in ViewListEventPush:', viewListError);
            // }

            // productData = json_encode(productData);
            // localStorage.setItem("productData"+window.TALLY_WEBSITE_COUNTRY_INITIAL, JSON.stringify(productData));
            // document.cookie = "productData1='test data'; expires=" + expires + "; path=/";
        } catch (error) {
            console.warn('GA Tracking: Error in setProductCookie:', error);
        }

        // const expires = new Date(Date.now() + 60 * 60 * 1000).toUTCString(); 
        //document.cookie = "productData=" + encodeURIComponent(JSON.stringify(productMap)) + "; path=/; expires=" + expires;
    }

    function getCookieProductData(productId) {

        // if (!cookie) return null;
        try {
            // prepare a json array of product data with item id as key and product data as value

            return productData[productId] || null;
        } catch {
            return null;
        }
    }

    function getPlanDuration() {
        try {
            const monthQty = document.querySelector('#monthQty')?.value || 'NA';
            const multiYear = document.querySelector('#strHiddenMultiYearTSS')?.value || 'NA';
            if (monthQty != 'NA') return `${monthQty} Months`;
            if (multiYear != 'NA') return `${multiYear} Years`;
            return 'NA';
        } catch (error) {
            console.warn('GA Tracking: Error in getPlanDuration:', error);
            return 'NA';
        }
    }

    function getNearestSectionText(element) {
        try {
            if (!element) return '';

            let parent = element;
            // if (typeof $ !== 'undefined' && $(parent).data('section-text')) {
            //     return $(parent).data('section-text').trim();
            // }
            while (parent) {
                const section = parent.querySelector('.cls-section');
                if (section) return section.innerText.trim();
                parent = parent.parentElement;
            }
            return '';
        } catch (error) {
            console.warn('GA Tracking: Error in getNearestSectionText:', error);
            return '';
        }
    }

    function getNearestSubheaderText(element) {
        try {
            if (!element) return '';
            let parent = element;
            while (parent) {
                const subheader = parent.querySelector('.cls-subheader');
                if (subheader) return subheader.innerText.trim();
                parent = parent.parentElement;
            }
            return '';
        } catch (error) {
            console.warn('GA Tracking: Error in getNearestSubheaderText:', error);
            return '';
        }
    }


    function getNearestHeaderText(element) {
        try {
            if (!element) return '';

            let parent = element;
            // if (typeof $ !== 'undefined' && $(parent).data('header-text')) {
            //     return $(parent).data('header-text').trim();
            // }
            while (parent) {
                // Find the first .cls-header in descendants of parent
                const header = parent.querySelector('.cls-header');
                if (header && header.innerText.trim()) {
                    return header.innerText.trim();
                }
                parent = parent.parentElement;
            }
            return '';
        } catch (error) {
            console.warn('GA Tracking: Error in getNearestHeaderText:', error);
            return '';
        }
    }


    function updateClickEvent(element_id) {
        try {
            if (!element_id) return;

            var eventDetails = {};
            eventDetails['tally-prime-new-user'] = 'Tally Prime New User Download click count';
            eventDetails['tally-prime-existing-customer'] = 'Tally Prime existing User Download click count';
            eventDetails['tally-prime-edit-log-new-user'] = 'Tally Prime Edit Log New User Download click count';
            eventDetails['tally-prime-edit-log-existing-customer'] = 'Tally Prime Edit Log existing User Download click count';
            eventDetails['tally-prime-student'] = 'Tally Prime Student User Download click count';
            eventDetails['tally-prime-edit-log-student'] = 'Tally Prime Edit Log Student User Download click count';

            //if eventDetails array has the element_id, then only send the event to api
            if (!eventDetails[element_id]) return;

            var description = eventDetails[element_id] || 'Default event description';
            //url host need to be fetched dynamically 
            var urlhost = window.location.host;

            if (!urlhost) {
                console.warn('GA Tracking: Host not available for updateClickEvent');
                return;
            }

            fetch("https://" + urlhost + "/wp-content/themes/tally/api/website-event-tracking-api.php", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    element_id: element_id,
                    description: description
                })
            })
                .then(res => {
                    if (!res.ok) {
                        throw new Error(`HTTP error! status: ${res.status}`);
                    }
                    return res.json();
                })
                .then(data => console.log(data))
                .catch(error => {
                    console.warn('GA Tracking: Error in updateClickEvent:', error);
                });
        } catch (error) {
            console.warn('GA Tracking: Error in updateClickEvent:', error);
        }
    }

    function websiteAnalytics(eventType, event, productId = '') {
        try {
            if (!event || !eventType) {
                console.warn('GA Tracking: Invalid parameters for websiteAnalytics');
                return;
            }

            var clicked = event.currentTarget;
            var destPage = 'NA';
            var header = '';
            var section = '';
            var clickText = '';
            var subheader = '';
            var product = '';

            if (clicked) {
                try {
                    destPage = clicked.href || 'NA';
                    header = getNearestHeaderText(clicked)?.trim() || 'NA';
                    section = getNearestSectionText(clicked)?.trim() || 'NA';
                    clickText = clicked.innerText?.trim() || '';
                    subheader = getNearestSubheaderText(clicked)?.trim() || 'NA';
                    // var productElement = clicked.closest('.cls-product');
                    product = ProductNames[productId] ? ProductNames[productId] : '';
                } catch (clickedError) {
                    console.warn('GA Tracking: Error processing clicked element:', clickedError);
                }
            }

            if (eventType == 'purchase') {
                try {
                    destPage = 'https://tipl.' + window.location.host + '/cart/checkout/';
                    clickText = event.innerText?.trim() || '';
                    var cookieProduct = productId ? getCookieProductData(productId) : null;
                    var planDuration = getPlanDuration();
                    var productid = cookieProduct?.ITEM_ID || '';
                    var productName = cookieProduct?.FLD_NAME || '';
                    var productPrice = 0;

                    if (planDuration != 'NA') {
                        var period = planDuration.split(' ');
                        if (period.length > 1) {
                            //if it has month in its text, then multiply the price with the number of months.   
                            if (period[1].includes('Month') || period[1].includes('Months')) {
                                productPrice = cookieProduct?.FLD_PRICE || '';
                                productPrice = productPrice * parseInt(period[0]);
                            }
                            else {
                                productPrice = cookieProduct?.PRICE[period[0]] || '';

                                productPrice = productPrice * parseInt(period[0]) * 12; // Assuming the price is per year, multiply by 12 to get the total for the selected duration
                            }

                            // need to update discounted price for 3 months and 12 months rental india
                            if (period[0] == '3' && (productid == 41628 || productid == 41629))
                                productPrice = productPrice - (productPrice * 0.05); // Assuming the price is per year, multiply by 12 to get the total for the selected duration
                            else
                                if (period[0] == '12' && (productid == 41628 || productid == 41629))
                                    productPrice = productPrice - (productPrice * 0.1); // Assuming the price is per year, multiply by 12 to get the total for the selected duration

                        }
                    }
                    else
                        if (cookieProduct && cookieProduct.FLD_ITEM_TYPE == 45)//for TDE
                        {
                            productPrice = cookieProduct?.FLD_PRICE || '';
                            productPrice = productPrice * 12; // Assuming the price is per year, multiply by 12 to get the total for the selected duration
                        }
                        else
                            productPrice = cookieProduct?.FLD_PRICE || '';


                    if (productid == 41581 || productid == 41582) {
                        planDuration = "Lifetime";
                    }
                    productPrice = parseInt(productPrice) || 0; // Ensure productPrice is a number, default to 0 if not a number
                    var productCategory = cookieProduct?.FLAVOUR_NAME || 'NA';
                    var currency = cookieProduct?.FLD_CURRENCY || '';
                } catch (purchaseError) {
                    console.warn('GA Tracking: Error in purchase logic:', purchaseError);
                    // Set default values
                    destPage = 'https://tipl.' + window.location.host + '/cart/checkout/';
                    clickText = event.innerText?.trim() || '';
                    var productid = '';
                    var productName = '';
                    var productPrice = 0;
                    var planDuration = 'NA';
                    var productCategory = 'NA';
                    var currency = '';
                    //if ookieProduct.FLD_FLAVOUR_TYPE is 1 then set productcategor1 to Single User else set to Multi User
                    var productCategory1 = cookieProduct?.FLD_FLAVOUR_TYPE == 1 ? 'Single User' : 'Multi User';
                }
            }

            if (eventType == 'download') {
                try {
                    if (productId == "previous-version") {
                        // For previous version downloads, we need to get the product name from the dropdown which is visible to user.
                        // Find the select box that does not have 'd-none' class and is visible
                        var dropdowns = event.currentTarget?.parentElement?.previousElementSibling?.querySelectorAll('.dropdown-container');
                        var product = '';
                        if (dropdowns && dropdowns.length) {
                            dropdowns.forEach(function (dd) {
                                try {
                                    const style = window.getComputedStyle(dd);
                                    //check if select element is not hidden and is visible using:visible selector
                                    if (style.display !== "none") {
                                        //check if the div containing select field and get the select text out of the select input and pass to product variable
                                        product = dd.querySelector('select');
                                        if (product) {
                                            product = product.options[product.selectedIndex].text.trim();
                                        }
                                    }
                                } catch (dropdownError) {
                                    console.warn('GA Tracking: Error processing dropdown:', dropdownError);
                                }
                            });
                        }
                        var productName = product || '';
                        var subheader = ProductNames[productId] || 'NA';
                    }
                    else
                        if (productId) {
                            if (productId == 'TE9' || productId == 'EDIT_LOG') {
                                var product = ProductNames[productId] + ' ' + section || '';
                                var productName = ProductNames[productId] + ' ' + section || '';
                            }
                            else
                                if (productId == 'TS9' || productId == 'TDE') {
                                    var product = section || '';
                                    var productName = section || '';
                                }
                                else {
                                    var product = ProductNames[productId] || '';
                                    var productName = ProductNames[productId] || '';
                                }
                            var subheader = ProductNames[productId] || 'NA';
                        }
                        else {
                            var product = section || '';
                            var productName = section || '';
                        }
                } catch (downloadError) {
                    console.warn('GA Tracking: Error in download logic:', downloadError);
                    // Set default values
                    var product = section || '';
                    var productName = section || '';
                    var subheader = ProductNames[productId] || 'NA';
                }
            }

            var currentPage = window.location.href;
            var prevPage = document.referrer || 'NA';


            var quantity = '1';
            var searchQuery = 'NA';
            if (eventType == 'searchSubmit') {
                try {
                    //get the value from s param of the url if exists else take input param
                    // var urlParams = new URLSearchParams(window.location.search);
                    // if (urlParams.has('s')) {
                    //     searchQuery = urlParams.get('s');
                    // } else {
                    var curele = event.currentTarget
                    //  if(event.currentTarget.classList.contains('track-searchSubmit')) {
                    searchQuery = event.currentTarget.value.trim() || '';
                    // }
                    // else
                    // if($(curele).parent().parent().find('.track-searchSubmit'))
                    // {
                    //      searchQuery = $(curele).parent().parent().find('.track-searchSubmit').val();
                    // }
                    // }


                    clickText = "Search";
                } catch (searchError) {
                    console.warn('GA Tracking: Error in searchSubmit logic:', searchError);
                    searchQuery = 'NA';
                    clickText = "Search";
                }
            }

            if (eventType == 'formSubmit') {
                try {
                    var userType = [];
                    userType['1'] = 'Business owner';
                    userType['3'] = 'Accountant';
                    userType['6'] = 'Student';
                    userType['7'] = 'Others';
                    //if form-type attribute is present, then use the value else use the header value
                    if (event.currentTarget.getAttribute('form-type'))
                        var formType = event.currentTarget.getAttribute('form-type').trim() || 'NA';
                    else
                        if (header)
                            var formType = header.trim() || 'NA';
                        else
                            var formType = 'NA';
                    //i need current events parent form tag
                    var form = event.currentTarget.closest('form');
                    if (form) {

                        var userTypeElement = form.querySelector('[name="userType"]');
                        if (userTypeElement) {
                            var selectedValue = userTypeElement.value;
                            subheader = userType[selectedValue] || 'NA';
                        }
                        //create same for strcampaignid element
                        var strCampaignIDElement = form.querySelector('[name="strCampaignID"]');
                        if (strCampaignIDElement) {
                            var selectedValue = strCampaignIDElement.value;
                            campaign = selectedValue || 'NA';
                        }
                    }

                    clickText = event.currentTarget.innerText?.trim() || 'NA';
                    //fetch section value from the current submits data attribute
                    var section = event.currentTarget.getAttribute('data-section') || 'NA';
                } catch (formError) {
                    console.warn('GA Tracking: Error in formSubmit logic:', formError);
                    var formType = header || 'NA';
                    clickText = event.currentTarget.innerText?.trim() || 'NA';
                    var section = event.currentTarget.getAttribute('data-section') || 'NA';
                }
            }

            if (eventType == 'click') {
                try {
                    //set section only if data-section attribute is present
                    if (event.currentTarget.getAttribute('data-section'))
                        var section = event.currentTarget.getAttribute('data-section') || 'NA';
                    //set header if data-header attribute is present
                    if (event.currentTarget.getAttribute('data-header'))
                        var header = event.currentTarget.getAttribute('data-header') || 'NA';
                    //set sub header if data-header attribute is present
                    if (event.currentTarget.getAttribute('data-subheader'))
                        var subheader = event.currentTarget.getAttribute('data-subheader') || 'NA';
                    //set click text if data-click-text attribute is present
                    if (event.currentTarget.getAttribute('click-text'))
                        var clickText = event.currentTarget.getAttribute('click-text') || 'NA';

                    //if header is 'Manage Subscriptions' then set the click text appended with previous element text
                    if (header == 'Manage subscriptions') {
                        clickText = event.currentTarget.previousElementSibling.innerText?.trim() + ' - ' + event.currentTarget.innerText?.trim() || 'NA';
                    }
                } catch (clickError) {
                    console.warn('GA Tracking: Error in click logic:', clickError);
                    // Set default values
                    var section = event.currentTarget.getAttribute('data-section') || 'NA';
                    var header = event.currentTarget.getAttribute('data-header') || 'NA';
                    var subheader = event.currentTarget.getAttribute('data-subheader') || 'NA';
                }
            }

            var downloadName = productName || 'Unknown Download';

            try {
                window.dataLayer = window.dataLayer || [];

                switch (eventType) {
                    case 'click':
                        window.dataLayer.push({
                            event: "section_interaction",
                            source_page_url: currentPage,
                            previous_page_url: prevPage,
                            destination_page_url: destPage,
                            header,
                            subheader,
                            section,
                            click_text: clickText,
                            company
                        });
                        //print only the section interaction data in alert to the verify the data
                        // console.log(window.dataLayer[window.dataLayer.length - 1]);
                        break;
                    case 'download':
                        window.dataLayer.push({
                            event: "download_click",
                            source_page_url: currentPage,
                            previous_page_url: prevPage,
                            destination_page_url: destPage,
                            header,
                            subheader,
                            download_name: downloadName,
                            click_text: clickText,
                            company
                        });
                        break;
                    case 'formSubmit':
                        window.dataLayer.push({
                            event: "lead_form_submit",
                            source_page_url: currentPage,
                            previous_page_url: prevPage,
                            destination_page_url: destPage,
                            header,
                            subheader,
                            section,
                            campaign,
                            form_type: formType,
                            click_text: clickText,
                            company
                        });
                        break;
                    case 'purchase':
                        window.dataLayer.push({
                            event: "purchase_intent_initiated",
                            source_page_url: currentPage,
                            previous_page_url: prevPage,
                            destination_page_url: destPage,
                            click_text: clickText,
                            plan_duration: planDuration,
                            user_pack: productCategory,
                            product_name: productName,
                            product_price: productPrice,
                            currency: currency,
                            quantity: quantity,
                            product_id: productid,
                            company
                        });
                        window.dataLayer.push({
                            event: "add_to_cart",
                            source_page_url: currentPage,
                            previous_page_url: prevPage,
                            destination_page_url: destPage,
                            click_text: clickText,
                            product: 'TallyPrime',
                            ecommerce: {
                                currency: currency,
                                value: productPrice,
                                items: [{
                                    item_id: productid,
                                    item_name: productName,
                                    affiliation: "Tally Solutions Pvt Ltd",
                                    coupon: "NA",
                                    discount: 0,
                                    index: 0,
                                    item_brand: "TallyPrime",
                                    item_category: productCategory,
                                    item_category1: productCategory1 || 'NA',
                                    item_category2: planDuration || 'NA',
                                    item_list_id: "NA",
                                    item_list_name: "NA",
                                    item_variant: "NA",
                                    price: productPrice,
                                    quantity: 1
                                }]
                            }
                        });
                        break;
                    case 'searchSubmit':
                        window.dataLayer.push({
                            event: "search_bar_submit",
                            source_page_url: currentPage,
                            previous_page_url: prevPage,
                            destination_page_url: destPage,
                            click_text: clickText,
                            search_query: searchQuery,
                            company
                        });
                        break;
                }
            } catch (dataLayerError) {
                console.warn('GA Tracking: Error pushing to dataLayer:', dataLayerError);
            }
        } catch (error) {
            console.warn('GA Tracking: Error in websiteAnalytics:', error);
        }
    }

    document.addEventListener('DOMContentLoaded', function () {
        try {
            // Check if event listeners are already attached
            if (window.GA_EVENT_LISTENERS_ATTACHED) {
                console.warn('GA Tracking: Event listeners already attached, skipping');
                return;
            }
            window.GA_EVENT_LISTENERS_ATTACHED = true;

            //if page has .itemId class then call setProductCookie()
            if (document.querySelector('.itemId')) {
                setProductCookie();
            }

            try {
                document.querySelectorAll('.track-click').forEach(el => {
                    // Check if this element already has our listener


                    el.addEventListener('click', function (event) {
                        try {
                            websiteAnalytics('click', event);
                        } catch (error) {
                            console.warn('GA Tracking: Error in track-click handler:', error);
                        }
                    });
                });
            } catch (error) {
                console.warn('GA Tracking: Error setting up track-click listeners:', error);
            }

            try {
                document.querySelectorAll('.ContentDownload').forEach(el => {
                    // Check if this element already has our listener


                    el.addEventListener('click', function (event) {
                        try {
                            const productId = el.getAttribute('data-product-id') || '';
                            const elementId = el.getAttribute('id') || '';
                            // updateClickEvent(elementId);
                            websiteAnalytics('download', event, productId);
                        } catch (error) {
                            console.warn('GA Tracking: Error in ContentDownload handler:', error);
                        }
                    });
                });
            } catch (error) {
                console.warn('GA Tracking: Error setting up ContentDownload listeners:', error);
            }

            try {
                document.querySelectorAll('.track-leadSubmit').forEach(el => {
                    // Check if this element already has our listener


                    el.addEventListener('click', function (event) {
                        try {
                            const productId = el.getAttribute('data-product-id') || '';
                            websiteAnalytics('formSubmit', event, productId);
                        } catch (error) {
                            console.warn('GA Tracking: Error in track-leadSubmit handler:', error);
                        }
                    });
                });
            } catch (error) {
                console.warn('GA Tracking: Error setting up track-leadSubmit listeners:', error);
            }

            try {
                document.querySelectorAll('.add_to_cart').forEach(el => {
                    // Check if this element already has our listener


                    el.addEventListener('click', function (event) {
                        try {
                            const productId = el.getAttribute('data-product-id') || '';
                            websiteAnalytics('purchase', event, productId);
                        } catch (error) {
                            console.warn('GA Tracking: Error in add_to_cart handler:', error);
                        }
                    });
                });
            } catch (error) {
                console.warn('GA Tracking: Error setting up add_to_cart listeners:', error);
            }

            try {
                document.querySelectorAll('.track-searchClick').forEach(el => {
                    // Check if this element already has our listener


                    el.addEventListener('click', function (event) {
                        try {
                            //  event.stopPropagation();
                            //if event keycode is enter, then only track the search submit
                            if (event.keyCode === 13) {
                                websiteAnalytics('searchSubmit', event);
                            }
                        } catch (error) {
                            console.warn('GA Tracking: Error in track-searchClick handler:', error);
                        }
                    });
                });
            } catch (error) {
                console.warn('GA Tracking: Error setting up track-searchClick listeners:', error);
            }

            try {
                //call the function when there is s= param in the url   
                var urlParams = new URLSearchParams(window.location.search);
                if (urlParams.has('s')) {
                    websiteAnalytics('searchSubmit', { currentTarget: document.querySelector('.track-searchSubmit') });
                }
                else {
                    document.querySelectorAll('.track-searchSubmit').forEach(el => {
                        // Check if this element already has our listener


                        el.addEventListener('keydown', function (event) {
                            try {
                                event.stopPropagation();
                                //if event keycode is enter, then only track the search submit
                                if (event.keyCode === 13) {
                                    websiteAnalytics('searchSubmit', event);
                                }
                            } catch (error) {
                                console.warn('GA Tracking: Error in track-searchSubmit handler:', error);
                            }
                        });
                    });
                }
            } catch (error) {
                console.warn('GA Tracking: Error setting up search functionality:', error);
            }
        } catch (error) {
            console.warn('GA Tracking: Error in DOMContentLoaded:', error);
        }
    });
    // i need a continous event listener for visisbility true of .price class on page scroll  and push to the data layer the price of the product
    document.addEventListener('scroll', function () {
        ViewListEventPush();
    });

    var visibleItemsMap = {}; // Map to store item_id -> {element, price} for visible items
    var uniquePriceMap = {}; // Track unique prices to avoid duplicates - maintained across calls

    function ViewListEventPush() {
        try {
            var priceElements = document.querySelectorAll('.price');
            if (!priceElements || priceElements.length === 0) return;

            var viewportHeight = window.innerHeight || document.documentElement.clientHeight;
            var viewportWidth = window.innerWidth || document.documentElement.clientWidth;
            var currentVisibleItems = {};

            // Initialize uniquePriceMap from existing visibleItemsMap if not already populated
            // Note: visibleItemsMap now uses uniqueKey as the key, so we can directly use those keys
            if (Object.keys(uniquePriceMap).length === 0 && Object.keys(visibleItemsMap).length > 0) {
                for (var key in visibleItemsMap) {
                    // The key is already the uniqueKey (itemId + '_' + price)
                    uniquePriceMap[key] = true;
                }
            }

            // Check each price element for visibility while scrolling
            for (var i = 0; i < priceElements.length; i++) {
                var priceElement = priceElements[i];
                try {
                    // Optimized visibility check - combine all checks
                    var rect = priceElement.getBoundingClientRect();
                    var style = window.getComputedStyle(priceElement);

                    // Combined visibility check
                    var isVisible = rect.top < viewportHeight &&
                        rect.bottom > 0 &&
                        rect.left < viewportWidth &&
                        rect.right > 0 &&
                        style.display !== 'none' &&
                        style.visibility !== 'hidden' &&
                        style.opacity !== '0' &&
                        priceElement.offsetWidth > 0 &&
                        priceElement.offsetHeight > 0;

                    if (!isVisible) continue;


                    // Extract and parse price
                    var itemPriceText = priceElement.textContent.trim().replace(/<[^>]*>?/g, '');
                    var itemPriceTextArray = itemPriceText.split(' ');
                    itemPriceText = itemPriceTextArray[itemPriceTextArray.length - 1];
                    itemPriceText = itemPriceText.replace(/[₹$€£,]/g, '').trim();
                    var itemPrice = parseFloat(itemPriceText) || 0;

                    // Skip if price is invalid
                    if (itemPrice <= 0) continue;

                    // Find plan duration - optimized parent traversal
                    var planDuration = 'Lifetime';
                    var parent = priceElement.parentElement;
                    var perpetualParent = parent ? parent.closest('.te9_perpetual') : null;

                    if (perpetualParent) {
                        planDuration = 'Lifetime';
                    } else {
                        while (parent) {
                            var monthElement = parent.querySelector('.clsNumOfMonths');
                            if (monthElement) {
                                planDuration = monthElement.value.trim() + ' Months';
                                break;
                            }
                            var yearElement = parent.querySelector('.clsMultiYearTSS');
                            if (yearElement) {
                                planDuration = yearElement.value.trim() + ' Years';
                                break;
                            }
                            parent = parent.parentElement;
                        }
                    }

                    // Find itemId element - optimized search
                    var itemIdElement = priceElement.closest('.itemId');
                    if (!itemIdElement) {
                        var cardContainer = priceElement.closest('.cardContainer');
                        if (cardContainer) {
                            itemIdElement = cardContainer.querySelector('.itemId');
                        }
                    }
                    if (!itemIdElement && priceElement.parentElement) {
                        itemIdElement = priceElement.parentElement.querySelector('.itemId');
                    }
                    if (!itemIdElement && priceElement.parentElement && priceElement.parentElement.parentElement) {
                        itemIdElement = priceElement.parentElement.parentElement.querySelector('.itemId');
                    }

                    if (!itemIdElement) continue;

                    var itemId = (itemIdElement.textContent || itemIdElement.value || '').trim();
                    if (!itemId) continue;

                    // Create unique key using itemId + price to identify unique items
                    var uniqueKey = itemId + '_' + itemPrice;

                    // Only add if this unique price combination hasn't been pushed to dataLayer yet
                    // Don't mark in uniquePriceMap here - only mark when actually pushed to dataLayer
                    if (!uniquePriceMap[uniqueKey]) {
                        // Store in currentVisibleItems - we'll check uniquePriceMap again when building items array
                        currentVisibleItems[uniqueKey] = {
                            itemId: itemId,
                            price: itemPrice,
                            element: itemIdElement,
                            planDuration: planDuration
                        };
                    }
                } catch (elementError) {
                    console.warn('GA Tracking: Error processing price element:', elementError);
                }
            }

            // Update the global visible items map
            visibleItemsMap = currentVisibleItems;
            var uniqueKeys = Object.keys(visibleItemsMap);

            if (uniqueKeys.length === 0) return;

            // Prepare array of items using getCookieProductData for each id
            // Only push items that are not already in uniquePriceMap (haven't been pushed to dataLayer yet)
            var items = [];
            var itemIndex = 0;
            for (var j = 0; j < uniqueKeys.length; j++) {
                var uniqueKey = uniqueKeys[j];
                try {
                    var visibleItem = visibleItemsMap[uniqueKey];
                    var id = visibleItem.itemId;
                    var itemPrice = visibleItem.price || 0;

                    var product = getCookieProductData(id);
                    if (!product) continue;

                    // If price is 0, try to get it from product data
                    if (itemPrice === 0 && product.FLD_PRICE) {
                        itemPrice = parseFloat(product.FLD_PRICE) || 0;
                        // Update uniqueKey with the new price from product data
                        uniqueKey = id + '_' + itemPrice;
                    }

                    // Check if this unique price combination has already been pushed to dataLayer
                    // Do this check AFTER updating uniqueKey with product price if needed
                    if (uniquePriceMap[uniqueKey]) continue;

                    // Mark as pushed to dataLayer BEFORE adding to items array
                    uniquePriceMap[uniqueKey] = true;

                    var usertype = product.FLD_FLAVOUR_TYPE == 1 ? 'Single User' : 'Multi User';

                    items.push({
                        item_id: id,
                        item_name: product.FLD_NAME,
                        in_stock: "Yes",
                        affiliation: "Tally Solutions Pvt Ltd",
                        coupon: "NA",
                        discount: 0,
                        index: itemIndex,
                        item_brand: "TallyPrime",
                        item_category: product.FLAVOUR_NAME || 'NA',
                        item_category1: usertype || 'NA',
                        item_category2: visibleItem.planDuration || 'NA',
                        price: itemPrice,
                        quantity: 1
                    });
                    itemIndex++;
                } catch (itemError) {
                    console.warn('GA Tracking: Error processing item:', uniqueKey, itemError);
                }
            }

            if (items.length > 0) {
                try {
                    window.dataLayer = window.dataLayer || [];
                    window.dataLayer.push({
                        event: "view_item_list",
                        source_page_url: window.location.href,
                        previous_page_url: document.referrer || 'NA',
                        destination_page_url: 'NA',
                        product: "TallyPrime",
                        ecommerce: {
                            item_list_id: items[0].item_name || 'NA',
                            item_list_name: items[0].item_category1 || 'NA',
                            items: items
                        }
                    });
                } catch (dataLayerError) {
                    console.warn('GA Tracking: Error pushing view_item_list to dataLayer:', dataLayerError);
                }
            }
        } catch (error) {
            console.warn('GA Tracking: Error in ViewListEventPush:', error);
        }
    }

} // End of GA_TRACKING_INITIALIZED check