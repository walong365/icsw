exports.config = {
  jasmineNodeOpts: {
    defaultTimeoutInterval: 90000
  },
  framework: 'jasmine',
  seleniumAddress: 'http://localhost:4444/wd/hub',
  specs: ['spec.js'],
  plugins: [{
    package: 'jasmine2-protractor-utils',
    disableHTMLReport: false,
    disableScreenshot: false,
    screenshotPath:'./reports/screenshots',
    screenshotOnExpectFailure:true,
    screenshotOnSpecFailure:true,
    clearFoldersBeforeTest: true,
    htmlReportDir: './reports/htmlReports'
  }]
};
