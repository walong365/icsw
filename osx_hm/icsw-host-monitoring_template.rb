class IcswHostMonitoring < Formula
  desc "OS X (darwin) port of the init.at icsw monitoring software"
  homepage "http://www.init.at"
  url URL_PLACEHOLDER
  version VERSION_PLACEHOLDER
  sha256 SHA256_PLACEHOLDER

  include Language::Python::Virtualenv

  depends_on "python"
  depends_on "memcached"
  depends_on "cavaliercoder/dmidecode/dmidecode"

  resource "six" do
    url "https://files.pythonhosted.org/packages/b3/b2/238e2590826bfdd113244a40d9d3eb26918bd798fc187e2360a8367068db/six-1.10.0.tar.gz"
    sha256 "105f8d68616f8248e24bf0e9372ef04d3cc10104f1980f54d57b2ce73a5ad56a"
  end

  resource "enum34" do
    url "https://pypi.python.org/packages/bf/3e/31d502c25302814a7c2f1d3959d2a3b3f78e509002ba91aea64993936876/enum34-1.1.6.tar.gz"
    sha256 "8ad8c4783bf61ded74527bffb48ed9b54166685e4230386a9ed9b1279e2df5b1"
  end
   
  resource "memcached" do
    url "https://pypi.python.org/packages/f7/62/14b2448cfb04427366f24104c9da97cf8ea380d7258a3233f066a951a8d8/python-memcached-1.58.tar.gz"
    sha256 "2775829cb54b9e4c5b3bbd8028680f0c0ab695db154b9c46f0f074ff97540eb6"
  end
  
  resource "lxml" do
    url "https://pypi.python.org/packages/4f/3f/cf6daac551fc36cddafa1a71ed48ea5fd642e5feabd3a0d83b8c3dfd0cb4/lxml-3.6.4.tar.gz"
    sha256 "61d5d3e00b5821e6cda099b3b4ccfea4527bf7c595e0fb3a7a760490cedd6172"
  end

  resource "Pygments" do
    url "https://pypi.python.org/packages/b8/67/ab177979be1c81bc99c8d0592ef22d547e70bb4c6815c383286ed5dec504/Pygments-2.1.3.tar.gz"
    sha256 "88e4c8a91b2af5962bfa5ea2447ec6dd357018e86e94c7d14bd8cacbc5b55d81"
  end

  resource "netifaces" do
    url "https://pypi.python.org/packages/a7/4c/8e0771a59fd6e55aac993a7cc1b6a0db993f299514c464ae6a1ecf83b31d/netifaces-0.10.5.tar.gz"
    sha256 "59d8ad52dd3116fcb6635e175751b250dc783fb011adba539558bd764e5d628b"
  end

  resource "psutil" do
    url "https://pypi.python.org/packages/78/cc/f267a1371f229bf16db6a4e604428c3b032b823b83155bd33cef45e49a53/psutil-4.3.1.tar.gz"
    sha256 "38f74182fb9e15cafd0cdf0821098a95cc17301807aed25634a18b66537ba51b"
  end

  resource "pyzmq" do
    url "https://pypi.python.org/packages/ab/3a/5826efd93ebbbdc33203f70c6ceebab1b58ac6cb1e1ab131cc6b990b4cfa/pyzmq-15.4.0.tar.gz"
    sha256 "9d1d69da7ee78dce8721a1617c7938ded1cd1df76a6c1abf19acebb1a5ccc2bf"
  end

  resource "setproctitle" do
    url "https://pypi.python.org/packages/5a/0d/dc0d2234aacba6cf1a729964383e3452c52096dc695581248b548786f2b3/setproctitle-1.1.10.tar.gz"
    sha256 "6283b7a58477dd8478fbb9e76defb37968ee4ba47b05ec1c053cb39638bd7398"
  end


  def install
    virtualenv_install_with_resources

    libexec.install Dir["opt"]

    system "ln -s #{libexec}/opt #{libexec}/lib/python2.7/site-packages"
  end


  plist_options :manual => "#{HOMEBREW_PREFIX}/opt/icsw-host-monitoring/bin/icsw-host-monitoring"

  def plist; <<-EOS.undent
    <?xml version="1.0" encoding="UTF-8"?>
    <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
    <plist version="1.0">
    <dict>
      <key>Label</key>
      <string>#{plist_name}</string>
      <key>KeepAlive</key>
      <true/>
      <key>ProgramArguments</key>
      <array>
        <string>#{opt_bin}/icsw-host-monitoring</string>
      </array>
      <key>RunAtLoad</key>
      <true/>
      <key>WorkingDirectory</key>
      <string>#{HOMEBREW_PREFIX}</string>
      <key>StandardErrorPath</key>
      <string>#{prefix}/icsw_host_monitoring_err.log</string>
      <key>StandardOutPath</key>
      <string>#{prefix}/icsw_host_monitoring.log</string>
    </dict>
    </plist>
    EOS
  end

  test do
    system "icsw-host-monitoring -h"
  end
end
