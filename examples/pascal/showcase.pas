program Showcase;
    const answer = 42;
    var i: integer;

    procedure show(n: integer);
        begin
            write('n = ');
            writeln(n)
        end;

    function triple(n: integer): integer;
        begin
            triple := 3 * n
        end;

begin
    writeln('int: ', answer, ' triple: ', triple(answer));
    show(7);
    write('booleans: ');
    writeln(true, ' ', false);
    write('real: ');
    writeln(2.5);
    for i := 1 to 3 do
        case i of
            1: writeln('one');
            2: writeln('two');
            3: writeln('three')
        end
end.
