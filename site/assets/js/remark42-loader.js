(function (c, d) {
  for (var i = 0; i < c.length; i++) {
    var s = d.createElement("script"), ext = ".js", h = d.head || d.body;
    if ("noModule" in s) { s.type = "module"; ext = ".mjs"; } else { s.async = true; }
    s.defer = true;
    s.src = remark_config.host + "/web/" + c[i] + ext;
    h.appendChild(s);
  }
})(remark_config.components, document);
