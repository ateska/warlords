import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.symbol.SourceType;
import java.nio.file.*;
public class Rename extends GhidraScript {
  public void run() throws Exception {
    for (String line : Files.readAllLines(Paths.get("funcs.txt"))) {
      line=line.trim(); if (line.isEmpty()) continue;
      Address a = currentProgram.getAddressFactory().getAddress(line);
      if (a!=null && getFunctionAt(a)==null) { disassemble(a); createFunction(a, null); }
    }
    for (String line : Files.readAllLines(Paths.get("names.txt"))) {
      String[] p=line.trim().split("\\s+"); if (p.length<2) continue;
      Address a = currentProgram.getAddressFactory().getAddress(p[0]);
      Function f = getFunctionAt(a);
      if (f==null) { disassemble(a); f=createFunction(a,null);} 
      if (f!=null) f.setName(p[1], SourceType.USER_DEFINED);
    }
  }
}
