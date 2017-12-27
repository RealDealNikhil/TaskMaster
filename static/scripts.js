// Highlight current page in navbar
$(document).ready(function() {
  // get current URL path and assign 'active' class
  var pathname = window.location.pathname;
  console.log(pathname);
  $('.navbar-nav > a[href="'+pathname+'"]').addClass('active');
  $('.navbar-nav > a[href="'+pathname+'"]')
    .append("<span class='sr-only'>(current)</span>");
})
