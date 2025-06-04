// src/types/Table.ts
export interface Column {
  name: string;
  type: string;
  nullable: boolean;
  primaryKey: boolean;
  foreignKey?: {
    table: string;
    column: string;
  };
}

export interface Table {
  name: string;
  columns: Column[];
}

export interface Relationship {
  from: {
    table: string;
    column: string;
  };
  to: {
    table: string;
    column: string;
  };
  type: 'ONE_TO_ONE' | 'ONE_TO_MANY' | 'MANY_TO_ONE' | 'MANY_TO_MANY';
}

export interface DatabaseSchema {
  tables: Table[];
  relationships: Relationship[];
}