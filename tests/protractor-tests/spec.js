describe('ICSW Basic Interface Tests:', function() {
  var EC = protractor.ExpectedConditions;

  var valid_device_name = undefined;
  var valid_group_name = undefined;

  function makeid()
  {
    var text = "";
    var possible = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz";

    for(var i=0; i < 10; i++)
        text += possible.charAt(Math.floor(Math.random() * possible.length));

    return text;
  }


  var icswHomepage = function() {
    var icsw_homepage_url = "http://192.168.1.245/";
    var login_username_field = element(by.model('login_data.username'));
    var login_password_field = element(by.model('login_data.password'));
   
    var login_button = element(by.xpath("//button[@type=\"submit\"]"));
    var login_button_is_clickable = EC.elementToBeClickable(login_button);

    var image_element = element(by.xpath("/html/body/icsw-layout-menubar/nav/div/icsw-menu-progress-bars/ul/li/img"));

    var overlay_element = element(by.xpath("/html/body/div[1]/div/div[1]"));

    this.overlay_element = overlay_element;

    this.select_all_devices_button = element(by.xpath("/html/body/icsw-layout-sub-menubar/nav/ul/li[2]/icsw-tools-button/button"));

    this.devices_menu_button = element(by.xpath('/html/body/icsw-layout-menubar/nav/div/icsw-menu/div/ul/li[1]'));
    this.device_information_menu_button = element(by.xpath('/html/body/icsw-layout-menubar/nav/div/icsw-menu/div/ul/li[1]/ul/li/div/div/ul[1]/li[3]/a'));
    this.device_tree_menu_button = element(by.xpath('/html/body/icsw-layout-menubar/nav/div/icsw-menu/div/ul/li[1]/ul/li/div/div/ul[1]/li[4]/a'));
    this.device_connections_menu_button = element(by.xpath('/html/body/icsw-layout-menubar/nav/div/icsw-menu/div/ul/li[1]/ul/li/div/div/ul[1]/li[5]/a'));
    this.device_configuration_menu_button = element(by.xpath('/html/body/icsw-layout-menubar/nav/div/icsw-menu/div/ul/li[1]/ul/li/div/div/ul[1]/li[6]/a'));
    this.network_menu_button = element(by.xpath('/html/body/icsw-layout-menubar/nav/div/icsw-menu/div/ul/li[1]/ul/li/div/div/ul[1]/li[7]/a'));


    this.get = function() {
      browser.get(icsw_homepage_url);
      browser.wait(login_button_is_clickable);
    };

    this.set_username = function(username) {
      login_username_field.sendKeys(username);
    };

    this.set_password = function(password) {
      login_password_field.sendKeys(password);
    };

    this.ensure_valid_login = function() {
      this.set_username("admin");
      this.set_password("init4u")
      login_button.click();

      browser.sleep(5000)
      var modal_dialog = element(by.className("modal-footer"));

      return modal_dialog.isPresent().then(function(is_present) {
        if (is_present) {
          element(by.className("btn-success")).click();
          browser.wait(EC.and(EC.elementToBeClickable(image_element), EC.invisibilityOf(overlay_element)));
          expect(browser.getTitle()).toEqual('Dashboard');
        } else {
         expect(browser.getTitle()).toEqual('Dashboard');
        }
      });
    };

    this.perform_login = function() {
      login_button.click();

      return browser.sleep(5000).then(function() {
        var modal_dialog = element(by.className("modal-footer"));

        modal_dialog.isPresent().then(function(is_present) {
          if (is_present) {
            element(by.className("btn-success")).click();
            browser.wait(EC.and(EC.elementToBeClickable(image_element), EC.invisibilityOf(overlay_element))).then(function () {})
          }
        });
      });
    }
  };

  //////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
  // Login Tests
  //////////////////////////////////////////////////////////////////////////////////////////////////////////////////////

  // Test login with valid user
  it('login with valid login should work', function() {
    browser.restart();
    browser.ignoreSynchronization = true;

    var icsw_homepage = new icswHomepage();
    icsw_homepage.get();

    icsw_homepage.set_username("admin");
    icsw_homepage.set_password("init4u");

    icsw_homepage.perform_login().then(function() {
      expect(browser.getTitle()).toEqual('Dashboard');
    });
  });

  // Test login with invalid user
  it ('login with invalid login should not work', function() {
    browser.restart();
    browser.ignoreSynchronization = true;

    var icsw_homepage = new icswHomepage();
    icsw_homepage.get();

    icsw_homepage.set_username("adasdioasiod");
    icsw_homepage.set_password("oasddsaoasas");

    icsw_homepage.perform_login().then(function() {
      expect(browser.getTitle()).toEqual('ICSW Login');
    });
  });

  //////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
  // "Add new Device" Tests
  //////////////////////////////////////////////////////////////////////////////////////////////////////////////////////

  it ('Add new device page should be present', function() {
    browser.restart();
    browser.ignoreSynchronization = true;

    var icsw_homepage = new icswHomepage();
    icsw_homepage.get();
   
    icsw_homepage.ensure_valid_login().then(function() {
      browser.wait(EC.elementToBeClickable(icsw_homepage.devices_menu_button));
      icsw_homepage.devices_menu_button.click();

      var add_new_device_button = element(by.xpath("/html/body/icsw-layout-menubar/nav/div/icsw-menu/div/ul/li[1]/ul/li/div/div/ul[1]/li[2]/a"));
      browser.wait(EC.elementToBeClickable(add_new_device_button));
      add_new_device_button.click();

      var create_device_button = element(by.buttonText("create Device"));
      browser.wait(EC.elementToBeClickable(create_device_button));

      expect(browser.getTitle()).toEqual("Add new Device");
    });
  });

  it ('Creating a new device should work', function() {
    browser.restart();
    browser.ignoreSynchronization = true;

    var icsw_homepage = new icswHomepage();
    icsw_homepage.get();

    icsw_homepage.ensure_valid_login().then(function() {
      expect(browser.getTitle()).toEqual('Dashboard');

      browser.wait(EC.elementToBeClickable(icsw_homepage.devices_menu_button));
      icsw_homepage.devices_menu_button.click();

      var add_new_device_button = element(by.xpath("/html/body/icsw-layout-menubar/nav/div/icsw-menu/div/ul/li[1]/ul/li/div/div/ul[1]/li[2]/a"));
      browser.wait(EC.elementToBeClickable(add_new_device_button));
      add_new_device_button.click();

      var create_device_button = element(by.buttonText("create Device"));
      browser.wait(EC.elementToBeClickable(create_device_button));

      var fqdn_field = element(by.model('device_data.full_name'));
      var devicegroup_field = element(by.model('device_data.device_group'));
      var comment_field = element(by.model('device_data.comment'));

      var fqdn = makeid();
      var devicegroup = makeid();
      var comment = makeid();

      fqdn_field.clear();
      fqdn_field.sendKeys(fqdn);

      devicegroup_field.clear();
      devicegroup_field.sendKeys(devicegroup);

      comment_field.clear();
      comment_field.sendKeys(comment);

      create_device_button.click();

      var popup_message_1 = element(by.xpath('//*[@id="toast-container"]/div[1]/div[2]/div'));
      var popup_message_2 = element(by.xpath('//*[@id="toast-container"]/div[2]/div[2]/div'));

      browser.wait(EC.presenceOf(popup_message_1)).then(function() {
        expect(popup_message_1.getText()).toContain(fqdn);
        expect(popup_message_1.getText()).toContain(comment);

        browser.wait(EC.presenceOf(popup_message_2)).then(function() {
          expect(popup_message_2.getText()).toContain(devicegroup);
          valid_device_name = fqdn;
          valid_group_name = devicegroup;
        });
      });
    });
  });

  it ('Creating a duplicate device should not work', function() {
    browser.restart();
    browser.ignoreSynchronization = true;

    var icsw_homepage = new icswHomepage();
    icsw_homepage.get();

    icsw_homepage.ensure_valid_login().then(function() {
      expect(browser.getTitle()).toEqual('Dashboard');

      browser.wait(EC.elementToBeClickable(icsw_homepage.devices_menu_button));
      icsw_homepage.devices_menu_button.click();

      var add_new_device_button = element(by.xpath("/html/body/icsw-layout-menubar/nav/div/icsw-menu/div/ul/li[1]/ul/li/div/div/ul[1]/li[2]/a"));
      browser.wait(EC.elementToBeClickable(add_new_device_button));
      add_new_device_button.click();

      var create_device_button = element(by.buttonText("create Device"));
      browser.wait(EC.elementToBeClickable(create_device_button));

      var fqdn_field = element(by.model('device_data.full_name'));
      var devicegroup_field = element(by.model('device_data.device_group'));
      var comment_field = element(by.model('device_data.comment'));

      var fqdn = makeid();
      var devicegroup = makeid();
      var comment = makeid();

      fqdn_field.clear();
      fqdn_field.sendKeys(fqdn);

      devicegroup_field.clear();
      devicegroup_field.sendKeys(devicegroup);

      comment_field.clear();
      comment_field.sendKeys(comment);

      create_device_button.click();

      var popup_message_1 = element(by.xpath('//*[@id="toast-container"]/div[1]/div[2]/div'));
      var popup_message_2 = element(by.xpath('//*[@id="toast-container"]/div[2]/div[2]/div'));

      browser.wait(EC.presenceOf(popup_message_1)).then(function() {
        expect(popup_message_1.getText()).toContain(fqdn);
        expect(popup_message_1.getText()).toContain(comment);

        browser.wait(EC.presenceOf(popup_message_2)).then(function() {
          expect(popup_message_2.getText()).toContain(devicegroup);

          browser.wait(EC.not(EC.presenceOf(popup_message_1)));
          browser.wait(EC.not(EC.presenceOf(popup_message_2)));

          fqdn_field.clear();
          fqdn_field.sendKeys(fqdn);

          devicegroup_field.clear();
          devicegroup_field.sendKeys(devicegroup);

          comment_field.clear();
          comment_field.sendKeys(comment);

          create_device_button.click();

          var popup_message_single = element(by.xpath('//*[@id="toast-container"]/div/div[2]/div'));

          browser.wait(EC.presenceOf(popup_message_single)).then(function () {
            expect(fqdn_field.getAttribute('value')).toEqual(fqdn);
          });
        });
      });
    });
  });

  //////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
  // "Device Information" Tests
  //////////////////////////////////////////////////////////////////////////////////////////////////////////////////////

  it ('Device information page should work', function() {
    browser.restart();
    browser.ignoreSynchronization = true;

    var icsw_homepage = new icswHomepage();
    icsw_homepage.get();

    icsw_homepage.ensure_valid_login().then(function() {
      browser.wait(EC.and(EC.elementToBeClickable(icsw_homepage.devices_menu_button), EC.invisibilityOf(icsw_homepage.overlay_element)));
      icsw_homepage.devices_menu_button.click();

      browser.wait(EC.and(EC.elementToBeClickable(icsw_homepage.device_information_menu_button), EC.invisibilityOf(icsw_homepage.overlay_element)));
      icsw_homepage.device_information_menu_button.click();

      var title = "Device Information";
      browser.wait(EC.titleIs(title));

      var status_text_element = element(by.xpath("/html/body/div[3]/div/icsw-simple-device-info/div/div/div/span"));
      browser.wait(EC.and(EC.textToBePresentInElement(status_text_element, "No devices selected"), EC.invisibilityOf(icsw_homepage.overlay_element)));

      expect(status_text_element.getText()).toEqual("No devices selected");

      browser.wait(EC.and(EC.elementToBeClickable(icsw_homepage.select_all_devices_button), EC.invisibilityOf(icsw_homepage.overlay_element)));
      icsw_homepage.select_all_devices_button.click();


      var list_of_elements = element(by.xpath("/html/body/div[3]/div/icsw-simple-device-info/div/div/ul"));
      browser.wait(EC.and(EC.presenceOf(list_of_elements), EC.textToBePresentInElement(list_of_elements, valid_group_name)));
    });
  });

  //////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
  // "Device Tree" Tests
  //////////////////////////////////////////////////////////////////////////////////////////////////////////////////////

  // Check if creating a new device group works
  it ('Creating a new devicegroup should work', function() {
    browser.restart();
    browser.ignoreSynchronization = true;

    var icsw_homepage = new icswHomepage();
    icsw_homepage.get();

    icsw_homepage.ensure_valid_login().then(function() {
      browser.wait(EC.elementToBeClickable(icsw_homepage.devices_menu_button));
      icsw_homepage.devices_menu_button.click();

      browser.wait(EC.elementToBeClickable(icsw_homepage.device_tree_menu_button));
      icsw_homepage.device_tree_menu_button.click();

      var create_device_group_button = element(by.xpath("/html/body/div[3]/div/div/icsw-device-tree-overview/div/div/div/button[2]"));
      browser.wait(EC.and(EC.elementToBeClickable(create_device_group_button), EC.invisibilityOf(icsw_homepage.overlay_element)));
      create_device_group_button.click();

      var create_button = element(by.buttonText("Create"));
      browser.wait(EC.and(EC.elementToBeClickable(create_button), EC.invisibilityOf(icsw_homepage.overlay_element)));

      var group_name_field = element(by.model('edit_obj.name'));
      var group_description_field = element(by.model('edit_obj.description'));

      var group_name = makeid();
      var group_description = makeid();

      group_name_field.clear();
      group_name_field.sendKeys(group_name);

      group_description_field.clear();
      group_description_field.sendKeys(group_description);

      create_button.click();
      browser.sleep(1000);

      var filter_field = element(by.model("filter_settings.str_filter"));
      filter_field.sendKeys(group_name);
      browser.sleep(1000);

      var group_name_element = element(by.xpath("/html/body/div[3]/div/div/icsw-device-tree-overview/div/div/table/tbody/tr/td[1]/strong"));
      var description_element = element(by.xpath("/html/body/div[3]/div/div/icsw-device-tree-overview/div/div/table/tbody/tr/td[3]"));

      expect(group_name_element.getText()).toEqual(group_name);
      expect(description_element.getText()).toEqual(group_description);
    });
  });

  // check if creating a device works
  it ('Creating a new device should work', function() {
    browser.restart();
    browser.ignoreSynchronization = true;

    var icsw_homepage = new icswHomepage();
    icsw_homepage.get();

    icsw_homepage.ensure_valid_login().then(function() {
      browser.wait(EC.elementToBeClickable(icsw_homepage.devices_menu_button));
      icsw_homepage.devices_menu_button.click();

      browser.wait(EC.elementToBeClickable(icsw_homepage.device_tree_menu_button));
      icsw_homepage.device_tree_menu_button.click();

      var create_device_button = element(by.xpath("/html/body/div[3]/div/div/icsw-device-tree-overview/div/div/div/button[1]"));
      browser.wait(EC.and(EC.elementToBeClickable(create_device_button), EC.invisibilityOf(icsw_homepage.overlay_element)));
      create_device_button.click();

      var create_button = element(by.buttonText("Create"));
      browser.wait(EC.and(EC.elementToBeClickable(create_button), EC.invisibilityOf(icsw_homepage.overlay_element)));

      var name_field = element(by.model('edit_obj.name'));
      var description_field = element(by.model('edit_obj.comment'));

      var name = makeid();
      var description = makeid();

      name_field.clear();
      name_field.sendKeys(name);

      description_field.clear();
      description_field.sendKeys(description);

      create_button.click();

      var cancel_button = element(by.buttonText("Cancel"));
      cancel_button.click();

      browser.sleep(1000);

      var filter_field = element(by.model("filter_settings.str_filter"));
      filter_field.sendKeys(name);
      browser.sleep(1000);

      var group_name_element = element(by.xpath("/html/body/div[3]/div/div/icsw-device-tree-overview/div/div/table/tbody/tr/td[1]"));
      var description_element = element(by.xpath("/html/body/div[3]/div/div/icsw-device-tree-overview/div/div/table/tbody/tr/td[4]"));

      expect(group_name_element.getText()).toEqual(name);
      expect(description_element.getText()).toEqual(description);
    });
  });

  //////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
  // "Connections" tests
  //////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
  it ('Connections view should load', function() {
    browser.restart();
    browser.ignoreSynchronization = true;

    var icsw_homepage = new icswHomepage();
    icsw_homepage.get();

    icsw_homepage.ensure_valid_login().then(function () {
      browser.wait(EC.and(EC.elementToBeClickable(icsw_homepage.devices_menu_button, EC.invisibilityOf(icsw_homepage.overlay_element))));
      icsw_homepage.devices_menu_button.click();

      browser.wait(EC.and(EC.elementToBeClickable(icsw_homepage.device_connections_menu_button), EC.invisibilityOf(icsw_homepage.overlay_element)));
      icsw_homepage.device_connections_menu_button.click();

      var title = 'Device Connections';

      browser.wait(EC.titleIs(title));
      expect(browser.getTitle()).toEqual(title);
    });
  });

  //////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
  // "Assign Configurations" tests
  //////////////////////////////////////////////////////////////////////////////////////////////////////////////////////

  it ('Assigning configurations should work', function() {
    browser.restart();
    browser.ignoreSynchronization = true;

    var icsw_homepage = new icswHomepage();
    icsw_homepage.get();

    icsw_homepage.ensure_valid_login().then(function() {
      browser.wait(EC.and(EC.elementToBeClickable(icsw_homepage.devices_menu_button, EC.invisibilityOf(icsw_homepage.overlay_element))));
      icsw_homepage.devices_menu_button.click();

      browser.wait(EC.and(EC.elementToBeClickable(icsw_homepage.device_configuration_menu_button), EC.invisibilityOf(icsw_homepage.overlay_element)));
      icsw_homepage.device_configuration_menu_button.click();

      var title = 'Assign Configurations';

      browser.wait(EC.titleIs(title));
      expect(browser.getTitle()).toEqual(title);

      var input_field = element(by.xpath("/html/body/div[3]/div/icsw-device-configuration-overview/div[2]/div/input"));
      browser.wait(EC.and(EC.presenceOf(input_field), EC.invisibilityOf(icsw_homepage.overlay_element)));

      icsw_homepage.select_all_devices_button.click();

      var popup_message_single = element(by.xpath('//*[@id="toast-container"]/div/div[2]/div'));
      browser.wait(EC.and(EC.presenceOf(popup_message_single), EC.invisibilityOf(icsw_homepage.overlay_element)));
      browser.wait(EC.and(EC.not(EC.presenceOf(popup_message_single)), EC.invisibilityOf(icsw_homepage.overlay_element)));


      var config_button = element.all(by.className("glyphicon-minus")).first();
      browser.wait(EC.and(EC.presenceOf(config_button), EC.invisibilityOf(icsw_homepage.overlay_element)));
      config_button.click();

      browser.wait(EC.and(EC.presenceOf(popup_message_single), EC.invisibilityOf(icsw_homepage.overlay_element)));
      expect(popup_message_single.getText()).toEqual("added config auto-etc-hosts");
      browser.wait(EC.and(EC.not(EC.presenceOf(popup_message_single)), EC.invisibilityOf(icsw_homepage.overlay_element)));

      config_button = element(by.className("glyphicon-ok"));
      config_button.click();
      browser.wait(EC.and(EC.presenceOf(popup_message_single), EC.invisibilityOf(icsw_homepage.overlay_element)));
      expect(popup_message_single.getText()).toEqual("removed config auto-etc-hosts");
    });
  });

  //////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
  // "Network" tests
  //////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
  it ('Creating a new netdevice should work', function() {
    browser.restart();
    browser.ignoreSynchronization = true;

    var icsw_homepage = new icswHomepage();
    icsw_homepage.get();

    icsw_homepage.ensure_valid_login().then(function() {
      // get into network page
      browser.wait(EC.and(EC.elementToBeClickable(icsw_homepage.devices_menu_button, EC.invisibilityOf(icsw_homepage.overlay_element))));
      icsw_homepage.devices_menu_button.click();

      browser.wait(EC.and(EC.elementToBeClickable(icsw_homepage.network_menu_button), EC.invisibilityOf(icsw_homepage.overlay_element)));
      icsw_homepage.network_menu_button.click();

      // select known device
      var select_devices_button = element(by.xpath("/html/body/icsw-layout-sub-menubar/nav/ul/li[2]/span[2]"));
      browser.wait(EC.and(EC.elementToBeClickable(select_devices_button), EC.invisibilityOf(icsw_homepage.overlay_element)));
      select_devices_button.click();

      var input_field = element(by.model("struct.search_str"));

      var use_in_network_button = element(by.partialButtonText("Use in Network"));
      var clear_button = element(by.partialButtonText("Clear"));

      browser.wait(EC.presenceOf(use_in_network_button));
      input_field.sendKeys(valid_device_name);

      browser.wait(EC.presenceOf(clear_button));
      use_in_network_button.click();

      // wait for popup message, wait for popup message to go away
      var popup_message_single = element(by.xpath('//*[@id="toast-container"]/div/div[2]/div'));
      browser.wait(EC.and(EC.presenceOf(popup_message_single), EC.invisibilityOf(icsw_homepage.overlay_element)));
      browser.wait(EC.and(EC.not(EC.presenceOf(popup_message_single)), EC.invisibilityOf(icsw_homepage.overlay_element)));

      // push create button
      var create_button = element.all(by.partialButtonText("create")).first();
      browser.wait(EC.and(EC.elementToBeClickable(create_button), EC.invisibilityOf(icsw_homepage.overlay_element)));
      create_button.click();

      var dropdown_menu = element(by.className("dropdown-menu"));
      browser.wait(EC.presenceOf(dropdown_menu));


      // push "Netdevice" link in dropdown menu
      var create_netdevice_button = element(by.linkText("Netdevice"));
      create_netdevice_button.click();

      // wait for modal dialog to popup, enter a random name and create netdevice
      create_button = element(by.partialButtonText("Create"));
      browser.wait(EC.and(EC.elementToBeClickable(create_button), EC.invisibilityOf(icsw_homepage.overlay_element)));

      var netdevicename = makeid();

      input_field = element(by.model("edit_obj.devname"));
      input_field.clear();
      input_field.sendKeys(netdevicename);

      create_button.click();

      // check if netdevice was created
      browser.wait(EC.and(EC.presenceOf(popup_message_single), EC.invisibilityOf(icsw_homepage.overlay_element)));
      expect(popup_message_single.getText()).toEqual("created new netdevice '" + netdevicename + "'");
    });
  });
});