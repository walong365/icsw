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
    var icsw_homepage_url = browser.params.url;
    var login_username_field = element(by.model('login_data.username'));
    var login_password_field = element(by.model('login_data.password'));
   
    var login_button = element(by.xpath("//button[@type=\"submit\"]"));
    var login_button_is_clickable = EC.elementToBeClickable(login_button);

    var image_element = element(by.xpath("/html/body/icsw-layout-menubar/nav/div/icsw-menu-progress-bars/ul/li/img"));

    var overlay_element = element(by.xpath("/html/body/div[1]"));

    this.overlay_element = overlay_element;

    this.select_all_devices_button = element(by.xpath("/html/body/icsw-layout-sub-menubar/nav/ul/li[2]/icsw-tools-button[2]/button"));

    this.devices_menu_button = element(by.xpath('/html/body/icsw-layout-menubar/nav/div/icsw-menu/div/ul/li[1]'));
    this.device_information_menu_button = element(by.xpath('/html/body/icsw-layout-menubar/nav/div/icsw-menu/div/ul/li[1]/ul/li/div/div/ul[1]/li[3]/a'));
    this.device_tree_menu_button = element(by.xpath('/html/body/icsw-layout-menubar/nav/div/icsw-menu/div/ul/li[1]/ul/li/div/div/ul[1]/li[4]/a'));

    this.device_assign_configuration_menu_button = element(by.xpath('/html/body/icsw-layout-menubar/nav/div/icsw-menu/div/ul/li[1]/ul/li/div/div/ul[1]/li[5]/a'));
    this.network_menu_button = element(by.xpath('/html/body/icsw-layout-menubar/nav/div/icsw-menu/div/ul/li[1]/ul/li/div/div/ul[1]/li[6]/a'));

    this.device_power_controlling_connections_menu_button = element(by.xpath('/html/body/icsw-layout-menubar/nav/div/icsw-menu/div/ul/li[1]/ul/li/div/div/ul[2]/li[6]/a'));

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
      this.set_password("abc123");

      return this.perform_login(true);
    };

    this.perform_login = function(ensure_logged_in_status) {
      login_button.click();

      var deferred = protractor.promise.defer();

      var modal_backdrop = element(by.xpath("/html/body/div[5]"));

      browser.wait(EC.presenceOf(modal_backdrop), 10 * 1000).then(function() {
        var yes_button = element(by.className("btn-success"));
        browser.wait(EC.and(EC.elementToBeClickable(yes_button), EC.invisibilityOf(overlay_element))).then(function() {
          //console.log("clicking yes button");
          yes_button.click();
          browser.wait(EC.and(EC.titleIs('Dashboard'), EC.invisibilityOf(overlay_element))).then(function() {
            expect(browser.getTitle()).toEqual('Dashboard');
            //console.log("logged in");
            deferred.fulfill("ok")
          });
        });
      }, function() {
        if (ensure_logged_in_status == true) {
          expect(browser.getTitle()).toEqual('Dashboard');
          //console.log("logged in");
        }

        deferred.fulfill("ok")
      });

      return deferred.promise
    }
  };

  //////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
  // Login Tests
  //////////////////////////////////////////////////////////////////////////////////////////////////////////////////////

  // Test login with valid user
  it('login with valid login should work', function() {
    browser.restart();
    browser.driver.manage().window().maximize();
    browser.ignoreSynchronization = true;

    var icsw_homepage = new icswHomepage();
    icsw_homepage.get();

    icsw_homepage.set_username("admin");
    icsw_homepage.set_password("abc123");

    icsw_homepage.perform_login(false).then(function() {
      expect(browser.getTitle()).toEqual('Dashboard');
    });
  });

  // Test login with invalid user
  it ('login with invalid login should not work', function() {
    browser.restart();
    browser.driver.manage().window().maximize();
    browser.ignoreSynchronization = true;

    var icsw_homepage = new icswHomepage();
    icsw_homepage.get();

    icsw_homepage.set_username("adasdioasiod");
    icsw_homepage.set_password("oasddsaoasas");

    icsw_homepage.perform_login(false).then(function() {
      expect(browser.getTitle()).toEqual('ICSW Login');
    });
  });

  //////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
  // "Add new Device" Tests
  //////////////////////////////////////////////////////////////////////////////////////////////////////////////////////

  it ('Add new device page should be present', function() {
    browser.restart();
    browser.driver.manage().window().maximize();
    browser.ignoreSynchronization = true;

    var icsw_homepage = new icswHomepage();
    icsw_homepage.get();
   
    icsw_homepage.ensure_valid_login().then(function() {
      browser.wait(EC.and(EC.elementToBeClickable(icsw_homepage.devices_menu_button), EC.invisibilityOf(icsw_homepage.overlay_element))).then(function() {
        icsw_homepage.devices_menu_button.click();


        var add_new_device_button = element(by.xpath("/html/body/icsw-layout-menubar/nav/div/icsw-menu/div/ul/li[1]/ul/li/div/div/ul[1]/li[2]/a"));
        browser.wait(EC.and(EC.elementToBeClickable(add_new_device_button), EC.invisibilityOf(icsw_homepage.overlay_element))).then(function() {
          add_new_device_button.click();

          var create_device_button = element(by.buttonText("create Device"));
          browser.wait(EC.and(EC.elementToBeClickable(create_device_button), EC.invisibilityOf(icsw_homepage.overlay_element))).then(function() {
            expect(browser.getTitle()).toEqual("Add new Device");
          });
        });
      });
    });
  });

  it ('Creating a new device should work (in "Add new Device")', function() {
    browser.restart();
    browser.driver.manage().window().maximize();
    browser.ignoreSynchronization = true;

    var icsw_homepage = new icswHomepage();
    icsw_homepage.get();

    icsw_homepage.ensure_valid_login().then(function() {
      browser.wait(EC.and(EC.elementToBeClickable(icsw_homepage.devices_menu_button), EC.invisibilityOf(icsw_homepage.overlay_element))).then(function() {
        icsw_homepage.devices_menu_button.click();

        var add_new_device_button = element(by.xpath("/html/body/icsw-layout-menubar/nav/div/icsw-menu/div/ul/li[1]/ul/li/div/div/ul[1]/li[2]/a"));
        browser.wait(EC.and(EC.elementToBeClickable(add_new_device_button), EC.invisibilityOf(icsw_homepage.overlay_element))).then(function() {

          add_new_device_button.click();

          var create_device_button = element(by.buttonText("create Device"));
          browser.wait(EC.elementToBeClickable(create_device_button)).then(function() {
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

            var toast_container = element(by.xpath('//*[@id="toast-container"]'));
            var expected_text = "created new device '" + fqdn + " (" + comment + ")'";
            browser.wait(EC.textToBePresentInElement(toast_container, expected_text)).then(function(){
              valid_device_name = fqdn;
              valid_group_name = devicegroup;
            })
          });
        });
      });
    });
  });

  it ('Creating a duplicate device should not work', function() {
    browser.restart();
    browser.driver.manage().window().maximize();
    browser.ignoreSynchronization = true;

    var icsw_homepage = new icswHomepage();
    icsw_homepage.get();

    icsw_homepage.ensure_valid_login().then(function() {
      browser.wait(EC.and(EC.elementToBeClickable(icsw_homepage.devices_menu_button), EC.invisibilityOf(icsw_homepage.overlay_element))).then(function() {
        icsw_homepage.devices_menu_button.click();

        var add_new_device_button = element(by.xpath("/html/body/icsw-layout-menubar/nav/div/icsw-menu/div/ul/li[1]/ul/li/div/div/ul[1]/li[2]/a"));
        browser.wait(EC.and(EC.elementToBeClickable(add_new_device_button), EC.invisibilityOf(icsw_homepage.overlay_element))).then(function() {
          add_new_device_button.click();

          var create_device_button = element(by.buttonText("create Device"));
          browser.wait(EC.and(EC.elementToBeClickable(create_device_button), EC.invisibilityOf(icsw_homepage.overlay_element))).then(function() {

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

            var toast_container = element(by.xpath('//*[@id="toast-container"]'));
            var expected_text = "created new device '" + fqdn + " (" + comment + ")'";
            browser.wait(EC.textToBePresentInElement(toast_container, expected_text)).then(function() {
              browser.wait(EC.and(EC.elementToBeClickable(create_device_button), EC.invisibilityOf(icsw_homepage.overlay_element))).then(function() {
                fqdn_field.clear();
                fqdn_field.sendKeys(fqdn);

                devicegroup_field.clear();
                devicegroup_field.sendKeys(devicegroup);

                comment_field.clear();
                comment_field.sendKeys(comment);

                create_device_button.click();

                var expected_text = "device " + fqdn + " (" + comment + ") already exists";
                browser.wait(EC.textToBePresentInElement(toast_container, expected_text));
              });
            });
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
    browser.driver.manage().window().maximize();
    browser.ignoreSynchronization = true;

    var icsw_homepage = new icswHomepage();
    icsw_homepage.get();

    icsw_homepage.ensure_valid_login().then(function() {
      browser.wait(EC.and(EC.elementToBeClickable(icsw_homepage.devices_menu_button), EC.invisibilityOf(icsw_homepage.overlay_element))).then(function() {
        icsw_homepage.devices_menu_button.click();

        browser.wait(EC.and(EC.elementToBeClickable(icsw_homepage.device_information_menu_button), EC.invisibilityOf(icsw_homepage.overlay_element))).then(function() {
          icsw_homepage.device_information_menu_button.click();

          var title = "Device Information";
          browser.wait(EC.titleIs(title)).then(function() {
            browser.wait(EC.and(EC.elementToBeClickable(icsw_homepage.select_all_devices_button), EC.invisibilityOf(icsw_homepage.overlay_element))).then(function() {
              icsw_homepage.select_all_devices_button.click();

              var list_of_elements = element(by.xpath("/html/body/div[3]/div/icsw-simple-device-info/div/div/ul"));
              browser.wait(EC.and(EC.presenceOf(list_of_elements), EC.textToBePresentInElement(list_of_elements, valid_group_name)));
            });
          });
        });
      });
    });
  });

  //////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
  // "Device Tree" Tests
  //////////////////////////////////////////////////////////////////////////////////////////////////////////////////////

  // Check if creating a new device group works
  it ('Creating a new devicegroup should work', function() {
    browser.restart();
    browser.driver.manage().window().maximize();
    browser.ignoreSynchronization = true;

    var icsw_homepage = new icswHomepage();
    icsw_homepage.get();

    icsw_homepage.ensure_valid_login().then(function() {
      browser.wait(EC.and(EC.elementToBeClickable(icsw_homepage.devices_menu_button), EC.invisibilityOf(icsw_homepage.overlay_element))).then(function() {
        icsw_homepage.devices_menu_button.click();

        browser.wait(EC.and(EC.elementToBeClickable(icsw_homepage.device_tree_menu_button), EC.invisibilityOf(icsw_homepage.overlay_element))).then(function() {
          icsw_homepage.device_tree_menu_button.click();

          var create_device_group_button = element(by.xpath("/html/body/div[3]/div/div/icsw-device-tree-overview/div/div/div/button[2]"));
          browser.wait(EC.and(EC.elementToBeClickable(create_device_group_button), EC.invisibilityOf(icsw_homepage.overlay_element))).then(function() {
            create_device_group_button.click();

            var create_button = element(by.buttonText("Create"));

            browser.wait(EC.and(EC.elementToBeClickable(create_button), EC.invisibilityOf(icsw_homepage.overlay_element))).then(function() {
              var group_name_field = element(by.model('edit_obj.name'));
              var group_description_field = element(by.model('edit_obj.description'));

              var group_name = makeid();
              var group_description = makeid();

              group_name_field.clear();
              group_name_field.sendKeys(group_name);

              group_description_field.clear();
              group_description_field.sendKeys(group_description);

              create_button.click();

              var modal_backdrop = element(by.xpath("/html/body/div[5]"));

              browser.wait(EC.and(EC.stalenessOf(modal_backdrop), EC.invisibilityOf(icsw_homepage.overlay_element))).then(function() {
                var filter_field = element(by.model("filter_settings.str_filter"));
                filter_field.sendKeys(group_name);

                var tree_table = element(by.xpath("/html/body/div[3]/div/div/icsw-device-tree-overview/div/div/table"));
                browser.wait(EC.and(EC.textToBePresentInElement(tree_table, group_name), EC.textToBePresentInElement(tree_table, group_description)));
              });
            });
          });
        });
      });
    });
  });

  // check if creating a device works
  it ('Creating a new device should work (in "Device Tree")', function() {
    browser.restart();
    browser.driver.manage().window().maximize();
    browser.ignoreSynchronization = true;

    var icsw_homepage = new icswHomepage();
    icsw_homepage.get();

    icsw_homepage.ensure_valid_login().then(function() {
      browser.wait(EC.and(EC.elementToBeClickable(icsw_homepage.devices_menu_button), EC.invisibilityOf(icsw_homepage.overlay_element))).then(function() {
        icsw_homepage.devices_menu_button.click();

        browser.wait(EC.and(EC.elementToBeClickable(icsw_homepage.device_tree_menu_button), EC.invisibilityOf(icsw_homepage.overlay_element))).then(function() {
          icsw_homepage.device_tree_menu_button.click();

          var create_device_button = element(by.xpath("/html/body/div[3]/div/div/icsw-device-tree-overview/div/div/div/button[1]"));
          browser.wait(EC.and(EC.elementToBeClickable(create_device_button), EC.invisibilityOf(icsw_homepage.overlay_element))).then(function(){
            create_device_button.click();

            var create_button = element(by.buttonText("Create"));
            browser.wait(EC.and(EC.elementToBeClickable(create_button), EC.invisibilityOf(icsw_homepage.overlay_element))).then(function() {
              var name_field = element(by.model('edit_obj.name'));
              var description_field = element(by.model('edit_obj.comment'));

              var name = makeid();
              var description = makeid();

              name_field.clear();
              name_field.sendKeys(name);

              description_field.clear();
              description_field.sendKeys(description);

              create_button.click();

              var modal_backdrop = element(by.xpath("/html/body/div[5]"));
              browser.wait(EC.and(EC.stalenessOf(modal_backdrop), EC.invisibilityOf(icsw_homepage.overlay_element))).then(function() {
                var filter_field = element(by.model("filter_settings.str_filter"));
                filter_field.sendKeys(name);

                var tree_table = element(by.xpath("/html/body/div[3]/div/div/icsw-device-tree-overview/div/div/table"))
                browser.wait(EC.and(EC.textToBePresentInElement(tree_table, name), EC.textToBePresentInElement(tree_table, description)));
              });
            });
          });
        });
      });
    });
  });

  //////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
  // "Power Controlling Connections" tests
  //////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
  it ('Power Controlling Connections view should load', function() {
    browser.restart();
    browser.driver.manage().window().maximize();
    browser.ignoreSynchronization = true;

    var icsw_homepage = new icswHomepage();
    icsw_homepage.get();

    icsw_homepage.ensure_valid_login().then(function () {
      browser.wait(EC.and(EC.elementToBeClickable(icsw_homepage.devices_menu_button), EC.invisibilityOf(icsw_homepage.overlay_element))).then(function() {
        icsw_homepage.devices_menu_button.click();

        browser.wait(EC.and(EC.elementToBeClickable(icsw_homepage.device_power_controlling_connections_menu_button), EC.invisibilityOf(icsw_homepage.overlay_element))).then(function() {
          icsw_homepage.device_power_controlling_connections_menu_button.click();

          var title = 'Power Controlling Connections';

          browser.wait(EC.titleIs(title)).then(function() {
            expect(browser.getTitle()).toEqual(title);
          });
        });
      });
    });
  });

  //////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
  // "Assign Configurations" tests
  //////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
  it ('Assigning configurations should work', function() {
    browser.restart();
    browser.driver.manage().window().maximize();
    browser.ignoreSynchronization = true;

    var icsw_homepage = new icswHomepage();
    icsw_homepage.get();

    icsw_homepage.ensure_valid_login().then(function() {
      browser.wait(EC.and(EC.elementToBeClickable(icsw_homepage.devices_menu_button), EC.invisibilityOf(icsw_homepage.overlay_element))).then(function() {
        icsw_homepage.devices_menu_button.click();

        browser.wait(EC.and(EC.elementToBeClickable(icsw_homepage.device_assign_configuration_menu_button), EC.invisibilityOf(icsw_homepage.overlay_element))).then(function() {
          icsw_homepage.device_assign_configuration_menu_button.click();

          var title = 'Assign Configurations';

          browser.wait(EC.titleIs(title)).then(function() {
            var input_field = element(by.xpath("/html/body/div[3]/div/div/icsw-device-configuration-overview/div[2]/div/input"));
            browser.wait(EC.presenceOf(input_field)).then(function() {
              browser.wait(EC.and(EC.elementToBeClickable(icsw_homepage.select_all_devices_button), EC.invisibilityOf(icsw_homepage.overlay_element))).then(function() {
                icsw_homepage.select_all_devices_button.click();

                var toast_container = element(by.xpath('//*[@id="toast-container"]'));

                var config_button = element.all(by.className("glyphicon-minus")).first();
                browser.wait(EC.and(EC.elementToBeClickable(config_button), EC.invisibilityOf(icsw_homepage.overlay_element))).then(function() {
                  config_button.click();

                  browser.wait(EC.textToBePresentInElement(toast_container, "added config auto-etc-hosts")).then(function() {
                    config_button = element(by.className("glyphicon-ok"));
                    browser.wait(EC.and(EC.elementToBeClickable(config_button), EC.invisibilityOf(icsw_homepage.overlay_element))).then(function() {
                      config_button.click();

                      browser.wait(EC.textToBePresentInElement(toast_container, "removed config auto-etc-hosts"));
                    });
                  });
                });
              });
            });
          });
        });
      });
    });
  });

  //////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
  // "Network" tests
  //////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
  it ('Creating a new netdevice should work', function() {
    browser.restart();
    browser.driver.manage().window().maximize();
    browser.ignoreSynchronization = true;

    var icsw_homepage = new icswHomepage();
    icsw_homepage.get();

    icsw_homepage.ensure_valid_login().then(function() {
      // get into network page
      browser.wait(EC.and(EC.elementToBeClickable(icsw_homepage.devices_menu_button), EC.invisibilityOf(icsw_homepage.overlay_element))).then(function() {
        //console.log("clicking devices_menu_button");
        icsw_homepage.devices_menu_button.click();
        browser.wait(EC.and(EC.elementToBeClickable(icsw_homepage.network_menu_button), EC.invisibilityOf(icsw_homepage.overlay_element))).then(function() {
          //console.log("clicking network_menu_button");
          icsw_homepage.network_menu_button.click();
          var select_devices_button = element(by.xpath("/html/body/icsw-layout-sub-menubar/nav/ul/li[2]/span[2]"));
          browser.wait(EC.and(EC.elementToBeClickable(select_devices_button), EC.invisibilityOf(icsw_homepage.overlay_element))).then(function() {
            //console.log("clicking select_devices_button");
            select_devices_button.click();

            var use_in_network_button = element(by.partialButtonText("Use in Network"));
            browser.wait(EC.presenceOf(use_in_network_button)).then(function() {
              var input_field = element(by.model("struct.search_str"));
              input_field.sendKeys(valid_device_name);

              var clear_button = element(by.partialButtonText("Clear"));
              browser.wait(EC.presenceOf(clear_button)).then(function() {
                use_in_network_button.click();

                // push create button
                var create_button = element.all(by.partialButtonText("create")).first();
                browser.wait(EC.and(EC.elementToBeClickable(create_button), EC.invisibilityOf(icsw_homepage.overlay_element))).then(function() {
                  create_button.click();
                  var dropdown_menu = element(by.className("dropdown-menu"));
                  browser.wait(EC.presenceOf(dropdown_menu)).then(function() {
                    // push "Netdevice" link in dropdown menu
                    var create_netdevice_button = element(by.linkText("Netdevice"));
                    create_netdevice_button.click();

                    // wait for modal dialog to popup, enter a random name and create netdevice
                    create_button = element(by.partialButtonText("Create"));
                    browser.wait(EC.and(EC.elementToBeClickable(create_button), EC.invisibilityOf(icsw_homepage.overlay_element))).then(function() {
                      var netdevicename = makeid();

                      input_field = element(by.model("edit_obj.devname"));
                      input_field.clear();
                      input_field.sendKeys(netdevicename);

                      create_button.click();

                      // check if netdevice was created
                      var toast_container = element(by.xpath('//*[@id="toast-container"]'));
                      browser.wait(EC.textToBePresentInElement(toast_container, "created new netdevice '" + netdevicename + "'"));
                    })
                  })
                })
              })
            })
          })
        })
      })
    })
  })
});