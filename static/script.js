$(document).ready(function() {
  // Page transition
  // https://www.abeautifulsite.net/a-clean-fade-in-effect-for-webpages
  $(function() {
    $('#mother').removeClass('fade-out');
  });
  // Highlight current page in navbar
  // Get current URL path and assign 'active' class
  var pathname = window.location.pathname;
  $('.navbar-nav > a[href="'+pathname+'"]').addClass('active');
  $('.navbar-nav > a[href="'+pathname+'"]')
    .append("<span class='sr-only'>(current)</span>");
})
