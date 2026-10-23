program Sum;
    var i: integer;
    var total: integer;

    function add(a: integer; b: integer): integer;
        begin
            add := a + b
        end;
begin
    total := 0;
    for i := 1 to 10 do
        total := add(total, i);
    if total = 55 then
        halt(total - 13)
    else
        halt(1)
end.
